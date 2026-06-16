
import pandas as pd


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

def main():
    series = pd.read_csv("../../data/message.txt", sep="\t")
    word = str(series.sample(n=1).values).replace("[","").replace("]","").replace("'","")
    tentativa = 0
    while tentativa < 6:
        guess = input("").lower()
        if guess not in series.values:
            print("palavra invalida")
            continue
        check_word(word,guess)
        if word == guess:
            print(check_word(word,guess))
            break
        print(check_word(word,guess))
        tentativa+=1

if __name__ == '__main__':
    main()
