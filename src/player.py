import json
import math
import random
import time
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from joblib import dump as _joblib_dump, load as _joblib_load
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
            automaticamente a partir do ranking de palavras. Em
            qualquer caso, o espaço de busca considerado continua
            sendo o dicionário inteiro -- `first_word` só força a
            abertura, não restringe as tentativas seguintes.

        correct_word : str
            Palavra correta a ser descoberta pela simulação.

        Returns
        -------
        tuple[int, tuple, bool, str]
            (número de tentativas, tupla com todos os chutes, vitória,
            palavra correta).
        """
        patterns = _get_pattern_matrix()
        possible_words = WORD_LIST["palavras"].values.tolist()
        row = 0
        info = Info()
        all_guesses = []
        correct_word = "".join(correct_word)
        while len(possible_words) > 0 and row < 6:
            if row == 0 and first_word:
                word = first_word
            else:
                word = select_next_word(all_guesses, possible_words)
            all_guesses.append(word)
            values = check_word(correct_word, word)
            add_info(info, values, word)
            possible_words = patterns.get(word, values, possible_words)
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
    def _read_row(self, page: Page, row: int) -> tuple:
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
        tuple[list[int], bool]
            (valores, confiável) -- ver `compvision.check_collors` e
            `compvision.predict_square`. `confiável` sinaliza se a
            leitura parece estável o bastante para ser usada, ou se
            provavelmente foi feita durante a animação de revelação
            do tabuleiro.
        """
        pass

    def _read_row_com_retentativa(self, page: Page, row: int, tentativas: int = 3, espera_extra: float = 1.0) -> list:
        """
        Lê o resultado de uma linha, tentando de novo (com uma espera
        extra) se a primeira leitura vier marcada como pouco
        confiável -- normalmente sinal de que a captura de tela
        aconteceu antes da animação de revelação do tabuleiro
        terminar, não de um problema real na palavra tentada.

        Parameters
        ----------
        page : Page
            Página do navegador controlada pelo Playwright.

        row : int
            Índice da linha a ser lida.

        tentativas : int, optional
            Número máximo de leituras a tentar antes de desistir e
            devolver a última leitura obtida mesmo assim.

        espera_extra : float, optional
            Segundos extras de espera antes de cada nova tentativa.

        Returns
        -------
        list[int]
            Resultado de cada uma das cinco posições da linha (a
            última leitura obtida, confiável ou não).
        """
        values, confiavel = self._read_row(page, row)
        tentativa = 1
        while not confiavel and tentativa < tentativas:
            time.sleep(espera_extra)
            values, confiavel = self._read_row(page, row)
            tentativa += 1
        return values

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
            Em qualquer caso, o espaço de busca considerado continua
            sendo o dicionário inteiro -- `first_word` só força a
            abertura, não restringe as tentativas seguintes.

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
        patterns = _get_pattern_matrix()
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
                if row == 0 and first_word:
                    word = first_word
                else:
                    word = select_next_word(all_guesses, possible_words)
                all_guesses.append(word)
                type_word(page, word)
                time.sleep(2.0)
                values = self._read_row_com_retentativa(page, row)
                if len(values) != 5:
                    raise ValueError(
                        f"A leitura da linha {row} devolveu {len(values)} "
                        f"valores em vez de 5 ({values}) -- provavelmente uma "
                        "cor não reconhecida no tabuleiro. Encerrando em vez "
                        "de continuar com uma leitura incompleta, que faria "
                        "a partida terminar em derrota sem motivo real."
                    )
                add_info(info, values, word)
                possible_words = patterns.get(word, values, possible_words)
                row += 1
            win = "".join(info.correct).isalpha()
        return row, tuple(all_guesses), win, correct_word


class PlayOnWebsite(PlayOnWebsiteBase):
    """Estratégia que joga no navegador identificando o resultado de
    cada linha por análise direta das cores dos quadrados (visão
    computacional simples, sem deep learning)."""

    def _read_row(self, page: Page, row: int) -> tuple:
        return check_collors(print_row(page, row))


class PlayOnWebsiteDeepLearning(PlayOnWebsiteBase):
    """Estratégia que joga no navegador identificando o resultado de
    cada linha através de um modelo de deep learning treinado para
    classificar os quadrados do tabuleiro."""

    def _read_row(self, page: Page, row: int) -> tuple:
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
    Acompanha as letras já confirmadas como corretas durante uma
    partida.

    Usado apenas para determinar, ao final, se a partida terminou em
    vitória (`"".join(info.correct).isalpha()`) -- a filtragem de
    palavras candidatas a cada tentativa é feita por `PatternMatrix`,
    que não depende deste objeto.

    Attributes
    ----------
    correct : list[str]
        Letras na posição correta. Posições ainda não descobertas
        contêm ".".
    """

    def __init__(self):
        self.correct = [".", ".", ".", ".", "."]


def _encode_pattern(values) -> int:
    """
    Codifica um padrão de resultado (5 valores em {0, 1, 2}) como um
    único inteiro em base 3 (0 a 242).

    `PatternMatrix.matrix` guarda um desses códigos por par de
    palavras em vez de uma tupla de 5 elementos: um array numérico
    (`dtype=int16`) serializa e desserializa muito mais rápido do que
    um array de objetos guardando ~2 milhões de tuplas Python, o que
    reduziu o arquivo de cache de ~38MB para menos de 5MB e o tempo
    de carregá-lo de ~5.7s para frações de segundo.

    Parameters
    ----------
    values : Sequence[int]
        Padrão de resultado com 5 valores em {0, 1, 2}.

    Returns
    -------
    int
        Código em base 3 equivalente, no intervalo [0, 242].
    """
    codigo = 0
    for v in values:
        codigo = codigo * 3 + v
    return codigo


class PatternMatrix:
    """
    Pré-calcula e armazena em cache o resultado de `check_word` para
    todos os pares (resposta, palpite) do dicionário de palavras.

    Tanto o cálculo de entropia quanto a filtragem de candidatas após
    uma tentativa dependem do resultado de `check_word(resposta,
    palpite)` para muitos pares -- e o resultado de cada par não muda
    entre partidas, já que depende só das duas palavras envolvidas.
    Pré-calcular essa matriz uma única vez (e reaproveitá-la via cache
    em disco entre execuções) evita refazer esse trabalho a cada
    partida, o que importa especialmente ao gerar o dataset (até 6
    tentativas × `len(WORD_LIST)` partidas simuladas).

    Também substitui `guess_word`/`generate_regex`: em vez de
    reconstruir as restrições conhecidas como uma expressão regular
    (uma segunda implementação da mesma lógica, que pode divergir de
    `check_word` em casos com letras repetidas), a filtragem consulta
    diretamente o resultado pré-calculado -- mais rápido e, por
    construção, sempre consistente com `check_word`.

    A primeira construção percorre `len(word_list) ** 2` pares (com o
    dicionário completo do projeto, algo em torno de 10s); o resultado
    fica em cache em `CACHE_PATH`, então execuções seguintes só
    carregam o arquivo, desde que a lista de palavras não tenha
    mudado (`load_or_build` reconstrói automaticamente se tiver).

    Attributes
    ----------
    word_list : list[str]
        Lista de palavras usada para construir a matriz -- usada para
        detectar se um cache em disco está desatualizado.
    idx : dict[str, int]
        Mapeia cada palavra para seu índice em `matrix`.
    matrix : numpy.ndarray
        `matrix[i, j]` é o padrão de resultado (tupla de 5 inteiros)
        de `check_word(word_list[i], word_list[j])`.
    lookup : dict[tuple[str, tuple], list[str]]
        Mapeia (palpite, padrão observado) para a lista de palavras
        que produziriam esse padrão se fossem a resposta correta.
    """

    CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "pattern_matrix.joblib"

    @classmethod
    def load_or_build(cls, palavras) -> "PatternMatrix":
        """
        Carrega a matriz do cache em disco se existir e ainda for
        válida para a lista de palavras atual; caso contrário,
        constrói do zero e salva em cache para as próximas execuções.

        Parameters
        ----------
        palavras : Iterable[str]
            Lista de palavras (dicionário atual) para a qual a matriz
            deve ser construída ou validada.

        Returns
        -------
        PatternMatrix
        """
        palavras = list(palavras)

        if cls.CACHE_PATH.exists():
            cache = _joblib_load(cls.CACHE_PATH)
            if cache.word_list == palavras:
                return cache
            # dicionário mudou desde que o cache foi gerado -- reconstrói

        matriz = cls(palavras)
        cls.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _joblib_dump(matriz, cls.CACHE_PATH)
        return matriz

    def __init__(self, word_list):
        """
        Parameters
        ----------
        word_list : Iterable[str]
            Lista de palavras para as quais todos os pares
            (resposta, palpite) serão pré-calculados.
        """
        self.word_list = list(word_list)
        self.idx = {palavra: i for i, palavra in enumerate(self.word_list)}
        n = len(self.word_list)
        self.matrix = np.empty((n, n), dtype=np.int16)
        self.lookup = {}

        for i, resposta in enumerate(self.word_list):
            for j, palpite in enumerate(self.word_list):
                codigo = _encode_pattern(check_word(resposta, palpite))
                self.matrix[i, j] = codigo
                self.lookup.setdefault((palpite, codigo), []).append(resposta)

    def get(self, guess: str, feedback, possible_words: list) -> list:
        """
        Filtra `possible_words` para as palavras que produziriam
        exatamente `feedback` se `guess` fosse tentado contra elas.

        Parameters
        ----------
        guess : str
            Palavra que foi tentada.

        feedback : Sequence[int]
            Resultado observado para `guess` (0/1/2 por posição).

        possible_words : list[str]
            Palavras que ainda satisfaziam as restrições antes desta
            tentativa.

        Returns
        -------
        list[str]
            Palavras de `possible_words` compatíveis com `feedback`,
            excluindo a própria `guess`.
        """
        codigo = _encode_pattern(feedback)
        candidatos = self.lookup.get((guess, codigo), [])
        ainda_possiveis = set(possible_words)
        return [w for w in candidatos if w in ainda_possiveis and w != guess]

    def entropy_ranking(self, possible_words: list) -> dict:
        """
        Calcula, para cada palavra do dicionário, a entropia (em
        bits) do padrão de resultado que ela produziria contra as
        palavras ainda possíveis -- equivalente ao que `calc_entropy`
        fazia, mas consultando `matrix` em vez de recalcular
        `check_word` para cada par, que é a parte mais cara do
        algoritmo (refeita a cada tentativa, exceto a primeira, de
        cada partida).

        Palavras que dividem o conjunto de possibilidades em mais
        grupos, de tamanhos mais equilibrados, geram mais informação
        (entropia mais alta) e por isso tendem a ser escolhas
        melhores para a próxima tentativa.

        Parameters
        ----------
        possible_words : list[str]
            Palavras que ainda satisfazem as restrições conhecidas.

        Returns
        -------
        dict
            Dicionário que associa cada palavra do dicionário à
            entropia (float) do padrão de resultado que ela geraria.
        """
        indices_possiveis = [self.idx[w] for w in possible_words]
        total = len(possible_words)
        ranking = {}

        for palpite in self.word_list:
            j = self.idx[palpite]
            counts = Counter(int(self.matrix[i, j]) for i in indices_possiveis)
            entropy = 0.0
            for count in counts.values():
                p = count / total
                entropy += p * math.log2(1 / p)
            ranking[palpite] = entropy

        return ranking


_PATTERN_MATRIX = None


def _get_pattern_matrix() -> PatternMatrix:
    """
    Devolve a `PatternMatrix` compartilhada por todas as estratégias,
    construindo-a (ou carregando-a do cache) na primeira chamada.

    Mesmo padrão de Lazy Initialization usado em
    `compvision._get_model`: construída no máximo uma vez por
    processo e reaproveitada em todas as partidas daquela sessão --
    o que importa aqui especialmente pelo menu interativo rodar em
    loop, jogando várias partidas na mesma execução.

    Returns
    -------
    PatternMatrix
    """
    global _PATTERN_MATRIX
    if _PATTERN_MATRIX is None:
        _PATTERN_MATRIX = PatternMatrix.load_or_build(WORD_LIST["palavras"])
    return _PATTERN_MATRIX


def select_next_word(previous_guesses: list, possible_words: list) -> str:
    """
    Decide qual será a próxima palavra tentada.

    Na primeira tentativa (quando ainda não há chutes anteriores),
    usa o ranking estático pré-calculado na coluna "valor" do
    dataset. Nas tentativas seguintes, recalcula um ranking por
    entropia (via `PatternMatrix.entropy_ranking`) com base nas
    palavras ainda possíveis, o que tende a escolher a palavra que
    mais reduz o espaço de possibilidades. Quando restam poucas
    palavras candidatas, escolhe aleatoriamente entre elas, já que o
    cálculo de entropia deixa de compensar.

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
        ranking = _get_pattern_matrix().entropy_ranking(possible_words)

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
        calculada por `PatternMatrix.entropy_ranking` nas tentativas
        seguintes).

    Returns
    -------
    str
        Palavra escolhida.
    """
    possible_guesses = WORD_LIST[~WORD_LIST["palavras"].isin(guesses)]
    return max(possible_guesses["palavras"], key=ranking.get)


def check_word(word: str, guess: str):
    """
    Simula a lógica de avaliação do Termo.

    Retorna:
        2 -> letra correta na posição correta.
        1 -> letra existente em outra posição.
        0 -> letra inexistente.

    Utilizado quando a partida é simulada sem acessar o site, e para
    construir `PatternMatrix` (que pré-calcula esse resultado para
    todos os pares de palavras do dicionário).

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
    Atualiza `info.correct` com as letras confirmadas pelo resultado
    do último chute.

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