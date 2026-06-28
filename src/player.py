import re
import pandas as pd
from pathlib import Path
ROOT = Path("message.txt").resolve().parent.parent
PATH = ROOT/"data"/"message.txt"
PALAVRAS = pd.read_csv(PATH, sep="\t")

class Letras:
    def __init__(self):
        self.not_included = []
        self.correct = [".",".",".",".","."]
        self.missplaced = [[],[],[],[],[]]
        self.included = []

def rank():
    rank_l = PALAVRAS["palavras"].str.join('').str.split('').explode().value_counts()
    rank_words = {}
    for index, word in enumerate(PALAVRAS["palavras"]):
        rank_words[word] = 0
        for l in set(word):
            rank_words[word] += rank_l[l]

    return rank_words

def choose_word(guesses):
    rank_words = rank()
    guesses_ranked = {key: rank_words[key] for key in guesses}
    maior_valor = max(guesses_ranked.values())
    return next((palavra for palavra,valor in guesses_ranked.items() if valor == maior_valor ),None)


def filter_words(regex:str,word:str):
    return re.match(rf"{regex}",word)


def guess_word(info:object,guesses:list=None,) -> list:
    guess = "serao"
    if guesses:
        guess = choose_word(guesses)

    print(guess,end=" ", )

    if guess == word:
        return [guess]

    for index,value in enumerate(check_word(word,guess)):
        if value == 2:
            info.correct[index] = guess[index]
        if value == 1:
            info.missplaced[index].append(guess[index])
            if guess[index] in info.included:
                continue
            info.included.append(guess[index])
        if value == 0 and guess[index] not in info.correct and guess[index] not in info.included :
            info.not_included.append(guess[index])
    pattern = ""

    for index,elem in enumerate(info.correct):
        if (elem != ".") and not(info.missplaced[index]):
            pattern += elem
        elif info.missplaced[index]:
            pattern += f"[^{"".join(info.missplaced[index])}]"
        else:
            pattern += elem

    regex = f"^(?!.*[{"".join(info.not_included)}])" + "".join([f"(?=.*{x})" for x in info.included]) + pattern + "$"

    filter_guesses = PALAVRAS["palavras"].str.match(regex)
    guesses = PALAVRAS.loc[filter_guesses, "palavras"].tolist()
    if guess in guesses:
        guesses.remove(guess)
    print(guesses)
    return guesses


def main():
    word = str(PALAVRAS.sample(n=1).values).replace("[", "").replace("]", "").replace("'", "")
    print(word, end=":")
    tentativa = 0
    guesses = []
    info = Letras()
    while tentativa < 6:
        guesses = guess_word(word,info,guesses)

        if len(guesses) > 1 or len(guesses) == 0:
            tentativa+=1
        else:
            print(guesses[0],tentativa + 1)
            break



if __name__ == '__main__':
    main()
