import json
import math
import random
import re
import time
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd

from playwright.sync_api import sync_playwright, ViewportSize, Page

from compvision import check_collors, print_row, type_word, predict_square

# Caminho robusto para o dataset de palavras: sobe um nível a partir da
# pasta deste arquivo (src/) até a raiz do projeto e desce para data/.
# Usar pathlib evita depender de barras invertidas (Windows) ou do
# diretório em que o script foi iniciado.
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "data.csv"
WORD_LIST = pd.read_csv(DATA_PATH)


class SolutionStrategy(ABC):
    """
    Interface (padrão Strategy) para os diferentes modos de resolver
    o Termo.

    Cada estratégia concreta decide como a palavra é enviada ao jogo
    (terminal simulado ou navegador) e como o resultado de cada
    tentativa é obtido, mas todas expõem o mesmo contrato em `play`.
    """

    @abstractmethod
    def play(self, first_word: str = None, correct_word: str = None) -> tuple[int, tuple, bool, str]:
        """
        Executa uma partida completa do Termo.

        Parameters
        ----------
        first_word : str, optional
            Primeiro chute utilizado pelo algoritmo. Quando None, a
            primeira palavra é escolhida automaticamente a partir do
            ranking de palavras.

        correct_word : str, optional
            Palavra correta da partida (uso varia por estratégia).

        Returns
        -------
        tuple[int, tuple, bool, str]
            (
                número de tentativas,
                tupla contendo todos os chutes,
                vitória (True/False),
                palavra correta
            )
        """
        pass


class PlayOnTerminal(SolutionStrategy):
    """Estratégia que simula a partida inteiramente no terminal, sem
    abrir navegador, comparando os chutes contra uma palavra correta
    conhecida."""

    def play(self, first_word: str = None, correct_word: str = None):
        """
        Executa uma partida simulada no terminal.

        A cada tentativa, o resultado é calculado internamente por
        `check_word` (sem depender de navegador ou de visão
        computacional), o que torna esse modo o mais rápido para
        testes e para gerar o dataset de partidas.

        Parameters
        ----------
        first_word : str, optional
            Primeira palavra a ser tentada. Quando None, é escolhida
            automaticamente a partir do ranking de palavras.

        correct_word : str
            Palavra correta a ser descoberta pela simulação.

        Returns
        -------
        tuple[int, tuple, bool, str]
            (número de tentativas, tupla com todos os chutes, vitória,
            palavra correta).
        """
        if first_word:
            possible_words = [first_word]
        else:
            possible_words = WORD_LIST["palavras"].values.tolist()
        row = 0
        info = Info()
        all_guesses = []
        correct_word = "".join(correct_word)
        while len(possible_words) > 0 and row < 6:
            word = select_next_word(all_guesses, possible_words)
            all_guesses.append(word)
            values = check_word(correct_word, word)
            add_info(info, values, word)
            possible_words = guess_word(word, info, possible_words)
            row += 1
        win = "".join(info.correct).isalpha()
        return row, tuple(all_guesses), win, correct_word


class PlayOnWebsiteBase(SolutionStrategy):
    """
    Base (padrão Template Method) para as estratégias que jogam
    diretamente em https://term.ooo/ através do Playwright.

    Toda a orquestração do navegador — abrir o site, definir a
    palavra do dia via localStorage quando aplicável, digitar cada
    chute e controlar o laço de tentativas — é comum às duas
    estratégias baseadas em navegador. A única diferença entre elas é
    *como* o resultado de uma linha é lido (análise de cor simples ou
    modelo de deep learning), por isso essa etapa fica isolada no
    método `_read_row`, que cada subclasse implementa à sua maneira.
    """

    @abstractmethod
    def _read_row(self, page: Page, row: int) -> list:
        """
        Lê o resultado (0, 1 ou 2 por posição) de uma linha do
        tabuleiro já preenchida.

        Parameters
        ----------
        page : Page
            Página do navegador controlada pelo Playwright.

        row : int
            Índice da linha a ser lida (0 a 5).

        Returns
        -------
        list[int]
            Resultado de cada uma das cinco posições da linha.
        """
        pass

    def play(self, first_word: str = None, correct_word: str = None) -> tuple[int, tuple, bool, str]:
        """
        Executa uma partida completa do Termo no navegador.

        Pode jogar:
            - Ao vivo, contra a palavra do dia real do site (quando
              `correct_word` não é informado).
            - Em modo simulado, sobrescrevendo o localStorage do site
              para forçar a palavra correta informada.

        Parameters
        ----------
        first_word : str, optional
            Primeiro chute utilizado pelo algoritmo. Quando None, é
            escolhido automaticamente a partir do ranking de palavras.

        correct_word : str, optional
            Palavra correta da simulação. Quando informada, também é
            usada para alterar o localStorage e definir a solução do
            jogo; quando None, a partida é jogada contra a palavra
            real do dia no site.

        Returns
        -------
        tuple[int, tuple, bool, str]
            (número de tentativas, tupla com todos os chutes, vitória,
            palavra correta).
        """
        if first_word:
            possible_words = [first_word]
        else:
            possible_words = WORD_LIST["palavras"].values.tolist()
        row = 0
        info = Info()
        all_guesses = []
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
                word = select_next_word(all_guesses, possible_words)
                all_guesses.append(word)
                type_word(page, word)
                time.sleep(1.5)
                values = self._read_row(page, row)
                add_info(info, values, word)
                possible_words = guess_word(word, info, possible_words)
                row += 1
            win = "".join(info.correct).isalpha()
        return row, tuple(all_guesses), win, correct_word


class PlayOnWebsite(PlayOnWebsiteBase):
    """Estratégia que joga no navegador identificando o resultado de
    cada linha por análise direta das cores dos quadrados (visão
    computacional simples, sem deep learning)."""

    def _read_row(self, page: Page, row: int) -> list:
        return check_collors(print_row(page, row))


class PlayOnWebsiteDeepLearning(PlayOnWebsiteBase):
    """Estratégia que joga no navegador identificando o resultado de
    cada linha através de um modelo de deep learning treinado para
    classificar os quadrados do tabuleiro."""

    def _read_row(self, page: Page, row: int) -> list:
        return predict_square(print_row(page, row))


class Context:
    """
    Contexto do padrão Strategy: mantém a estratégia de jogo atual e
    delega a execução da partida a ela, permitindo trocar o modo de
    jogo (terminal, navegador, deep learning) sem alterar quem o
    utiliza.
    """

    def __init__(self, strategy: SolutionStrategy):
        """
        Parameters
        ----------
        strategy : SolutionStrategy
            Estratégia inicial a ser utilizada.
        """
        self._strategy = strategy

    def set_strategy(self, strategy: SolutionStrategy):
        """
        Troca a estratégia de jogo em uso.

        Parameters
        ----------
        strategy : SolutionStrategy
            Nova estratégia a ser utilizada nas próximas partidas.
        """
        self._strategy = strategy

    def play_strategy(self, first_word: str = None, correct_word: str = None):
        """
        Executa uma partida utilizando a estratégia atualmente
        configurada.

        Parameters
        ----------
        first_word : str, optional
            Primeira palavra a ser tentada.

        correct_word : str, optional
            Palavra correta da partida.

        Returns
        -------
        tuple[int, tuple, bool, str]
            Resultado retornado pela estratégia (ver `SolutionStrategy.play`).
        """
        return self._strategy.play(first_word, correct_word)


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
        self.correct = [".", ".", ".", ".", "."]
        self.missplaced = [[], [], [], [], []]
        self.included = []


def select_next_word(previous_guesses: list, possible_words: list) -> str:
    """
    Decide qual será a próxima palavra tentada.

    Na primeira tentativa (quando ainda não há chutes anteriores),
    usa o ranking estático pré-calculado na coluna "valor" do
    dataset. Nas tentativas seguintes, recalcula um ranking por
    entropia com base nas palavras ainda possíveis, o que tende a
    escolher a palavra que mais reduz o espaço de possibilidades.
    Quando restam poucas palavras candidatas, escolhe aleatoriamente
    entre elas, já que o cálculo de entropia deixa de compensar.

    Parameters
    ----------
    previous_guesses : list[str]
        Palavras já tentadas nesta partida.

    possible_words : list[str]
        Palavras que ainda satisfazem todas as restrições conhecidas.

    Returns
    -------
    str
        Próxima palavra a ser jogada.
    """
    if len(possible_words) <= 2:
        return random.choice(possible_words)

    if not previous_guesses:
        ranking = dict(zip(WORD_LIST["palavras"], WORD_LIST["valor"]))
    else:
        ranking = calc_entropy(possible_words)

    return choose_word(previous_guesses, ranking)


def choose_word(guesses, ranking: dict) -> str:
    """
    Escolhe a melhor palavra dentre as candidatas ainda não
    utilizadas.

    A escolha é feita a partir de `ranking`, um dicionário que
    associa cada palavra candidata a um valor numérico (quanto maior,
    melhor); a palavra com maior valor entre as que ainda não foram
    tentadas é a escolhida.

    Parameters
    ----------
    guesses : list[str]
        Palavras já tentadas, que devem ser excluídas das candidatas.

    ranking : dict
        Dicionário que associa cada palavra ao seu valor (score
        estático da coluna "valor" na primeira tentativa, ou entropia
        calculada por `calc_entropy` nas tentativas seguintes).

    Returns
    -------
    str
        Palavra escolhida.
    """
    possible_guesses = WORD_LIST[~WORD_LIST["palavras"].isin(guesses)]
    return max(possible_guesses["palavras"], key=ranking.get)


def calc_entropy(possible_words: list) -> dict:
    """
    Calcula, para cada palavra do dataset, a entropia (em bits) do
    padrão de resultado que ela produziria contra as palavras ainda
    possíveis.

    Palavras que dividem o conjunto de possibilidades em mais grupos,
    de tamanhos mais equilibrados, geram mais informação (entropia
    mais alta) e por isso tendem a ser escolhas melhores para a
    próxima tentativa.

    Parameters
    ----------
    possible_words : list[str]
        Palavras que ainda satisfazem as restrições conhecidas.

    Returns
    -------
    dict
        Dicionário que associa cada palavra do dataset à entropia
        (float) do padrão de resultado que ela geraria.
    """
    ranking = {}
    for guess in WORD_LIST["palavras"]:
        counts = Counter()

        for answer in possible_words:
            pattern = tuple(check_word(answer, guess))
            counts[pattern] += 1

        entropy = 0

        for count in counts.values():
            p = count / len(possible_words)
            entropy += p * math.log2(1 / p)

        ranking[guess] = entropy

    return ranking


def guess_word(guess: str, info: Info, possible_words: list) -> list:
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

    possible_words: list
        Lista de palavras possiveis

    Returns
    -------
    list[str]
        Lista de palavras que ainda satisfazem todas as restrições.
    """
    regex = generate_regex(info)
    pattern = re.compile(regex)

    if len(possible_words) == 1 and not (pattern.fullmatch(guess)):
        filter_guesses = WORD_LIST["palavras"].str.match(regex)
        possible_words = WORD_LIST.loc[filter_guesses, "palavras"].tolist()
    else:
        possible_words = [word for word in possible_words if pattern.fullmatch(word)]
    if guess in possible_words:
        possible_words.remove(guess)

    return possible_words


def generate_regex(info: Info) -> str:
    """
    Constrói a expressão regular que representa todas as restrições
    conhecidas sobre a palavra correta.

    Para cada posição, usa a letra correta quando já é conhecida, ou
    uma classe de negação com as letras que já se provaram fora de
    lugar naquela posição especificamente. Além disso, adiciona uma
    negação global para letras confirmadas ausentes e "lookaheads"
    positivos para letras confirmadas presentes em alguma posição
    ainda não determinada.

    Parameters
    ----------
    info : Info
        Estado atual da partida.

    Returns
    -------
    str
        Expressão regular que qualquer palavra candidata deve
        satisfazer (via `fullmatch`) para continuar sendo possível.
    """
    pattern = ""
    for index, elem in enumerate(info.correct):
        if elem.isalpha():
            pattern += elem
        elif info.missplaced[index]:
            pattern += f"[^{"".join(info.missplaced[index])}]"
        else:
            pattern += elem
    not_included = f"(?!.*[{"".join(info.not_included)}])" if info.not_included else ""
    included = "".join([f"(?=.*{x})" for x in info.included])
    regex = f"^{not_included}{included}{pattern}$"
    return regex


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
    for i1, l1 in enumerate(guess):
        if guess[i1] == word[i1]:
            values[i1] = 2
            guess[i1] = None
            word[i1] = None

    for i1, l1 in enumerate(guess):

        if guess[i1] in word and guess[i1] is not None:
            values[i1] = 1
            word[word.index(guess[i1])] = None
            guess[i1] = None

    return values


def add_info(info: Info, values: list, guess: str) -> None:
    """
    Atualiza o objeto `Info` com o resultado do último chute.

    Parameters
    ----------
    info : Info
        Estado atual da partida.

    values : list[int]
        Resultado retornado por `check_word`, `check_collors` ou
        `predict_square`.

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

    for index, value in enumerate(values):
        if value == 0 and guess[index] not in info.correct and guess[index] not in info.included and guess[index] not in info.not_included:
            info.not_included.append(guess[index])
