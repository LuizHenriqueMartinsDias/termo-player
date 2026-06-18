import random
import re

import pandas as pd
from pathlib import Path
ROOT = Path("message.txt").resolve().parent.parent
PATH = ROOT/"termo"/"data"/"message.txt"
PALAVRAS = pd.read_csv(PATH, sep="\t")

class Letras:
    def __init__(self):
        self.not_included = []
        self.correct = [".",".",".",".","."]
        self.missplaced = [[],[],[],[],[]]
        self.included = []

def check_letters():

    print(PALAVRAS["palavras"].str.join('').str.split('').explode().value_counts())
def check_word(word: str, guess: str):
    past_try = [0] * 5
    w = list(word)
    g = list(guess)
    for i1,l1 in enumerate(g):
        if g[i1] == w[i1]:
            past_try[i1] = 2
            g[i1] = None
            w[i1] = None

    for i1,l1 in enumerate(g):

        if g[i1] in w and g[i1] is not None:
            past_try[i1] = 1
            w[w.index(g[i1])] = None
            g[i1] = None

    return past_try

def filter_words(regex:str,word:str):
    return re.match(rf"{regex}",word)


def guess_word(word,info:object,guesses=None,) -> list:

    guess = "serao"

    if guesses:
        guess = random.choice(guesses)

    print(guess,end=" ", )

    if guess == word:
        return [guess]



    for index,value in enumerate(check_word(word,guess)):
        if value == 2:
            info.correct[index] = word[index]
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

    return guesses


def main():
    check_letters()
    word = str(PALAVRAS.sample(n=1).values).replace("[", "").replace("]", "").replace("'", "")
    print(word, end=":")
    tentativa = 1
    guesses = []
    info = Letras()
    while tentativa < 6:
        guesses = guess_word(word,info,guesses)

        if len(guesses) > 1 or len(guesses) == 0:
            tentativa+=1
        else:

            print(guesses[0],tentativa)
            break



if __name__ == '__main__':
    main()
