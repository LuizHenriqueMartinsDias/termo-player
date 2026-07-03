import os

import pandas as pd
import getopt, sys
import argparse

from player import WORD_LIST, Context, PlayOnTerminal, PlayOnWebsite,PlayOnWebsiteDeepLearning



def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("-s", "--save_dataset",
                        metavar="FIRST_WORD",
                        help="Salva um dataset usando a primeira palavra informada.")

    parser.add_argument("-t", "--play_terminal",
                        metavar="CORRECT_WORD",
                        help="Joga no terminal.")

    parser.add_argument("-b", "--play_browser",
                        metavar="CORRECT_WORD",
                        help="Joga no navegador.")

    parser.add_argument("-d", "--play_ml",
                        metavar="CORRECT_WORD",
                        nargs="?",
                        const=None,
                        help="Joga no navegador usando Deep Learning.")

    parser.add_argument("-f", "--first_word",
                        help="Define a primeira palavra.")

    args = parser.parse_args()

    context = Context(PlayOnTerminal())

    if args.save_dataset:
        context.set_strategy(PlayOnTerminal())

        for word in WORD_LIST["palavras"].values:
            dataset_args = context.play_strategy(
                first_word=args.save_dataset,
                correct_word=word
            )
            save_dataset(*dataset_args)

    elif args.play_terminal:
        context.set_strategy(PlayOnTerminal())
        context.play_strategy(
            first_word=args.first_word,
            correct_word=args.play_terminal
        )

    elif args.play_browser:
        context.set_strategy(PlayOnWebsite())
        context.play_strategy(
            first_word=args.first_word,
            correct_word=args.play_browser
        )

    elif args.play_ml is not None:
        context.set_strategy(PlayOnWebsiteDeepLearning())
        context.play_strategy(
            first_word=args.first_word,
            correct_word=args.play_ml
        )


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