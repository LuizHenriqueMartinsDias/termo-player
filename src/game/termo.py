import random
import re

import pandas as pd
from pathlib import Path
ROOT = Path("message.txt").resolve().parent.parent
PATH = ROOT/"termo"/"data"/"message.txt"
PALAVRAS = pd.read_csv(PATH, sep="\t")

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

def guess_word(word,guesses=None):

    guess = "audio"
    regex = list("^.....$")
    missplaced = ""

    if guesses is not None and len(guesses) > 0:
        guess = random.choice(list(guesses))
    print("chute: ",guess)
    if guess == word:
        return True

    for index,value in enumerate(check_word(word,guess)):
        if value == 2:
            regex[index+1] = word[index]
        if value == 1:
            missplaced += f"(?=.*{guess[index]})"

    if missplaced:
        regex.insert(1,missplaced)

    regexstr = "".join(regex)
    filter_guesses = PALAVRAS["palavras"].str.match(regexstr)
    guesses = PALAVRAS.loc[filter_guesses, "palavras"].tolist()
    print(regexstr)
    print("candidatas:", len(guesses),guesses)

    return guesses


def main():
    print(type(PALAVRAS))
    word = str(PALAVRAS.sample(n=1).values).replace("[", "").replace("]", "").replace("'", "")
    tentativa = 0
    guesses = None
    while tentativa < 6:
        resultado = guess_word(word, guesses)

        if resultado is True:
            print(f"Você ganhou! a palavra era {word}")
            break

        guesses = resultado
        tentativa += 1

if __name__ == '__main__':
    main()
