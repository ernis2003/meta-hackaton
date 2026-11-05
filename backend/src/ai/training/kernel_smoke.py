"""Framework-only synthetic CUDA/QLoRA check; NEVER qualifies the real 3B training gate."""
import tempfile
from pathlib import Path
from src.ai.common import ROOT, now, save_json


def main():
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if not torch.cuda.is_available():
        raise RuntimeError('No CUDA; CPU fallback disabled')
    torch.manual_seed(42)
    torch.cuda.reset_peak_memory_stats()
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    with tempfile.TemporaryDirectory() as temp:
        tiny = LlamaForCausalLM(LlamaConfig(vocab_size=128, hidden_size=128, intermediate_size=256,
            num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=128))
        tiny.save_pretrained(temp, safe_serialization=True)
        del tiny
        model = LlamaForCausalLM.from_pretrained(temp, device_map={'': 0}, torch_dtype=dtype,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype))
        model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant': False})
        model = get_peft_model(model, LoraConfig(r=4, lora_alpha=8, target_modules=['q_proj', 'v_proj'], task_type='CAUSAL_LM'))
        model.config.use_cache = False
        model.train()
        trainable = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(trainable, lr=.0002)
        data = torch.randint(0, 128, (1, 32), device='cuda')
        losses = []
        for _ in range(2):
            loss = model(input_ids=data, labels=data).loss
            loss.backward()
            assert any(p.grad is not None and torch.count_nonzero(p.grad).item() > 0 for p in trainable)
            optimizer.step(); optimizer.zero_grad()
            losses.append(loss.item())
        output = ROOT / 'artifacts' / 'framework_smoke_adapter'
        model.save_pretrained(output, safe_serialization=True)
        # Verify the installed TRL Trainer API and resumable checkpoint saving too.
        from datasets import Dataset
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from transformers import PreTrainedTokenizerFast
        from trl import SFTConfig, SFTTrainer
        tokenizer_core = Tokenizer(WordLevel({f't{i}': i for i in range(128)}, unk_token='t0'))
        tokenizer_core.pre_tokenizer = Whitespace()
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=tokenizer_core, pad_token='t0', eos_token='t1', unk_token='t0')
        dataset = Dataset.from_list([dict(prompt='t2 t3 t4 ', completion='t5 t6 t1') for _ in range(4)])
        training = SFTConfig(output_dir=str(Path(temp) / 'trainer'), max_steps=2,
            per_device_train_batch_size=1, gradient_accumulation_steps=1,
            max_length=32, save_steps=1, logging_steps=1, report_to='none',
            bf16=dtype == torch.bfloat16, fp16=dtype == torch.float16,
            completion_only_loss=True, gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant': False}, optim='paged_adamw_8bit')
        trainer = SFTTrainer(model=model, args=training, train_dataset=dataset, processing_class=tokenizer)
        trainer.train()
        checkpoint_saved = (Path(temp) / 'trainer' / 'checkpoint-2' / 'trainer_state.json').exists()
        result = dict(timestamp=now(), passed=(output / 'adapter_model.safetensors').exists(),
            scope='Synthetic tiny randomly initialized Llama; framework verification only, NOT official model smoke or fine-tuning results.',
            gpu=torch.cuda.get_device_name(0), torch=torch.__version__, cuda=torch.version.cuda,
            dtype=str(dtype), losses=losses, optimizer_steps=2,
            trl_optimizer_steps=trainer.state.global_step, trainer_checkpoint_saved=checkpoint_saved,
            peak_vram_bytes=torch.cuda.max_memory_allocated())
        result['passed'] = result['passed'] and checkpoint_saved
        save_json(ROOT / 'results' / 'framework_smoke.json', result)
        print(result)


if __name__ == '__main__':
    main()
