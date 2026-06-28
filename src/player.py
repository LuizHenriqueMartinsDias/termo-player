import json
import time

import pandas as pd
from pathlib import Path

from playwright.sync_api import sync_playwright, ViewportSize

from compvision import check_collors, print_row, type_word

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

def choose_word(guesses:list) -> list:
    rank_words = rank()
    guesses_ranked = {key: rank_words[key] for key in guesses}
    maior_valor = max(guesses_ranked.values())
    return next((palavra for palavra,valor in guesses_ranked.items() if valor == maior_valor ),None)


def guess_word(guess:list,info:Letras) -> list:
    print(guess)
    pattern = ""

    for index,elem in enumerate(info.correct):
        if elem.isalpha():
            pattern += elem
        elif info.missplaced[index]:
            pattern += f"[^{"".join(info.missplaced[index])}]"
        else:
            pattern += elem

    regex = f"^(?!.*[{"".join(info.not_included)}])" + "".join([f"(?=.*{x})" for x in info.included]) + pattern + "$"
    print(regex)
    filter_guesses = PALAVRAS["palavras"].str.match(regex)
    possible_words = PALAVRAS.loc[filter_guesses, "palavras"].tolist()
    if guess in possible_words:
        possible_words.remove(guess)
    print(possible_words)
    return possible_words


def add_info(info, values,guess):
    for index, value in enumerate(values):
        if value == 2:
            info.correct[index] = guess[index]
        if value == 1:
            info.missplaced[index].append(guess[index])
            if guess[index] in info.included:
                continue
            info.included.append(guess[index])
        if value == 0 and guess[index] not in info.correct and guess[index] not in info.included:
            info.not_included.append(guess[index])


def main():
    possible_words = PALAVRAS["palavras"].values.tolist()
    row = 0
    info = Letras()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=ViewportSize(width=1280, height=720),
        )
        page = context.new_page()
        palavra = "furia"

        local_storage_data = {"config": {"highContrast": 0, "hardMode": 0},
                              "meta": {"startTime": 1782623403199, "endTime": 0, "highContrastChange": 0},
                              "stats": {"games": 0, "wins": 0, "curstreak": 0, "avgtime": 0, "mintime": 0, "maxtime": 0,
                                        "maxstreak": 0, "histo": [0, 0, 0, 0, 0, 0]},
                              "state": [{"curday": 1638, "solution": f"{palavra}", "normSolution": f"{palavra}"}]}
        page.add_init_script(f" localStorage.setItem('termo', '{json.dumps(local_storage_data)}')")
        page.goto("https://term.ooo/")
        page.keyboard.press("Escape")
        while len(possible_words) > 0 and row<6:
            word = choose_word(possible_words)
            type_word(page,word)
            time.sleep(2)
            values = check_collors(print_row(page,row))
            add_info(info,values,word)
            possible_words = guess_word(word,info)
            row += 1

        return




if __name__ == '__main__':
    main()
