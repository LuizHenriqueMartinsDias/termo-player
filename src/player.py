import json
import time
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from playwright.sync_api import sync_playwright, ViewportSize

from src.compvision import check_collors, print_row, type_word

class Strategy(ABC):
    @abstractmethod
    def play(self,first_word:str=None, correct_word:str=None, website=True):
        pass
class ConcreteStrategyA(Strategy):
    def play(self,first_word: str = None, correct_word: str = None, website=True) -> tuple[int, tuple, bool, str]:
        """
           Executa uma partida completa do Termo.

           Pode jogar:
               - Diretamente no site utilizando Playwright.
               - Em modo simulado, comparando contra uma palavra informada.

           Parameters
           ----------
           first_word : str, optional
               Primeiro chute utilizado pelo algoritmo.

           correct_word : str, optional
               Palavra correta da simulação. Quando website=True,
               também pode ser utilizada para alterar o localStorage
               e definir a solução do jogo.

           website : bool, default=True
               Se True, joga automaticamente no site.
               Caso False, executa apenas uma simulação.

           Returns
           -------
           tuple
               (
                   número de tentativas,
                   tupla contendo todos os chutes,
                   vitória (True/False),
                   última palavra jogada
               )
           """

        if first_word:
            possible_words = [first_word]
        else:
            possible_words = WORD_LIST["palavras"].values.tolist()
        row = 0
        info = Info()
        all_guesses = []
        if website:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    viewport=ViewportSize(width=1280, height=720),
                )
                page = context.new_page()
                if correct_word:
                    page.clock.set_fixed_time("2026-06-29T12:00:00Z")
                    local_storage_data = {"config": {"highContrast": 0, "hardMode": 0},
                                          "meta": {"startTime": 1782623403199, "endTime": 0, "highContrastChange": 0},
                                          "stats": {"games": 0, "wins": 0, "curstreak": 0, "avgtime": 0, "mintime": 0,
                                                    "maxtime": 0,
                                                    "maxstreak": 0, "histo": [0, 0, 0, 0, 0, 0]},
                                          "state": [{"curday": 1639, "solution": f"{correct_word}",
                                                     "normSolution": f"{correct_word}"}]}
                    page.add_init_script(f" localStorage.setItem('termo', '{json.dumps(local_storage_data)}')")
                page.goto("https://term.ooo/")
                page.keyboard.press("Escape")

                while len(possible_words) > 0 and row < 6:
                    word = choose_word(possible_words)
                    all_guesses.append(word)
                    type_word(page, word)
                    time.sleep(2)
                    values = check_collors(print_row(page, row))
                    add_info(info, values, word)
                    possible_words = guess_word(word, info)
                    row += 1
                if "".join(info.correct).isalpha() and row < 7:
                    win = True
                else:
                    win = False
        else:
            while len(possible_words) > 0 and row < 6:
                word = choose_word(possible_words)
                all_guesses.append(word)
                values = check_word(correct_word, word)
                add_info(info, values, word)
                possible_words = guess_word(word, info)
                row += 1
            if "".join(info.correct).isalpha() and row < 7:
                win = True
            else:
                win = False
        return row, tuple(all_guesses), win, word


class Context:
    def __init__(self,strategy:Strategy):
        self._strategy = strategy
    def set_strategy(self,strategy:Strategy):
        self._strategy = strategy
    def play_strategy(self,first_word:str=None, correct_word:str=None, website=True):
       self._strategy.play(first_word,correct_word,website)

WORD_LIST = pd.read_csv("..\\data\\data.txt", sep="\t")

class Info:
    """
       Armazena todas as informações descobertas durante uma partida.

       Attributes
       ----------
       not_included : list[str]
           Letras que certamente não pertencem à palavra.

       correct : list[str]
           Letras na posição correta. Posições desconhecidas contêm ".".

       missplaced : list[list[str]]
           Para cada posição, guarda letras que pertencem à palavra,
           porém não podem ocupar aquela posição.

       included : list[str]
           Letras confirmadas na palavra, mas cuja posição ainda não
           foi totalmente determinada.
       """
    def __init__(self):
        self.not_included = []
        self.correct = [".",".",".",".","."]
        self.missplaced = [[],[],[],[],[]]
        self.included = []

def rank() -> dict:
    """
       Calcula uma pontuação para cada palavra do dicionário.

       A pontuação é baseada na frequência das letras em toda a lista
       de palavras. Letras repetidas contam apenas uma vez por palavra,
       incentivando palavras com maior cobertura de letras diferentes.

       Returns
       -------
       dict
           Dicionário no formato:
               {
                   palavra: pontuação
               }
       """
    rank_letters = WORD_LIST["palavras"].str.join('').str.split('').explode().value_counts()
    rank_words = {}
    for index, word in enumerate(WORD_LIST["palavras"]):
        rank_words[word] = 0
        for l in set(word):
            rank_words[word] += rank_letters[l]

    return rank_words

def choose_word(guesses:list) -> str:
    """
       Escolhe a melhor palavra dentre as candidatas.

       A escolha é feita utilizando o ranking calculado por `rank()`,
       priorizando palavras com letras mais frequentes.

       Parameters
       ----------
       guesses : list[str]
           Lista de palavras candidatas.

       Returns
       -------
       str
           Palavra escolhida.
       """

    rank_words = rank()
    if len(guesses) == 1 and not(str(guesses) in rank_words):
        return guesses[0]
    guesses_ranked = {key: rank_words[key] for key in guesses}
    max_value = max(guesses_ranked.values())
    return next((word for word,value in guesses_ranked.items() if value == max_value ),None)

def guess_word(guess:str, info:Info) -> list:
    """
    Filtra todas as palavras possíveis utilizando as informações
    descobertas até o momento.

    A filtragem é feita através de uma expressão regular construída
    dinamicamente.

    Parameters
    ----------
    guess : str
        Última palavra jogada.

    info : Info
        Estado atual da partida.

    Returns
    -------
    list[str]
        Lista de palavras que ainda satisfazem todas as restrições.
    """
    print(guess)
    pattern = ""

    for index,elem in enumerate(info.correct):
        if elem.isalpha():
            pattern += elem
        elif info.missplaced[index]:
            pattern += f"[^{"".join(info.missplaced[index])}]"
        else:
            pattern += elem
    not_included = f"(?!.*[{"".join(info.not_included)}])" if info.not_included else ""
    included = "".join([f"(?=.*{x})" for x in info.included])
    regex = f"^{not_included}{included}{pattern}$"
    print(regex)
    filter_guesses = WORD_LIST["palavras"].str.match(regex)
    possible_words = WORD_LIST.loc[filter_guesses, "palavras"].tolist()
    if guess in possible_words:
        possible_words.remove(guess)
    print(possible_words)
    return possible_words

def check_word(word: str, guess: str):
    """
       Simula a lógica de avaliação do Termo.

       Retorna:
           2 -> letra correta na posição correta.
           1 -> letra existente em outra posição.
           0 -> letra inexistente.

       Utilizado quando a partida é simulada sem acessar o site.

       Parameters
       ----------
       word : str
           Palavra correta.

       guess : str
           Palavra chutada.

       Returns
       -------
       list[int]
           Lista contendo o resultado de cada posição.
       """
    values = [0] * 5
    word: list[Optional[str]] = list(word)
    guess: list[Optional[str]] = list(guess)
    for i1,l1 in enumerate(guess):
        if guess[i1] == word[i1]:
            values[i1] = 2
            guess[i1] = None
            word[i1] = None

    for i1,l1 in enumerate(guess):

        if guess[i1] in word and guess[i1] is not None:
            values[i1] = 1
            word[word.index(guess[i1])] = None
            guess[i1] = None

    return values

def add_info(info:Info, values:list, guess:str) -> None:
    """
       Atualiza o objeto Letras com o resultado do último chute.

       Parameters
       ----------
       info : Info
           Estado atual da partida.

       values : list[int]
           Resultado retornado por check_word() ou check_collors().

       guess : str
           Palavra utilizada no chute.
       """

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








