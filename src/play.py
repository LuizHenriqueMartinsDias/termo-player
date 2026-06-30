import os

import pandas as pd

from src.player import play, WORD_LIST

def main():
    play()


def save_dataset(attempts:int, guesses:tuple, win:bool, correct_word:str) -> None:
    file = "dataset_01.csv"

    df = pd.DataFrame(data={"Palavra_correta": correct_word, "palavra_inicial": guesses[0], "N_de_tentativas":attempts, "Chutes": [guesses], "Vitoria":win})
    if os.path.exists(f"../data/{file}"):
        dataset = pd.read_csv(f"../data/{file}")
        dataset_temp = pd.concat([dataset,df],ignore_index=True)
        dataset = dataset_temp.drop_duplicates( subset=["Palavra_correta", "palavra_inicial"],keep='first').reset_index(drop=True)
        dataset.to_csv(f"../data/{file}", index=False)
        return
    df.to_csv(f"../data/{file}",index=False)

if __name__ == "__main__":
    main()