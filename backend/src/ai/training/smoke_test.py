from src.ai.training.train_qlora import arguments, train

if __name__ == '__main__':
    train(arguments(), smoke=True)
