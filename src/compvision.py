"""
Módulo de visão computacional do Termo.

Reúne as funções responsáveis por interagir com a página do jogo via
Playwright (digitar palavras, capturar o tabuleiro) e por interpretar
o resultado de cada tentativa, seja por análise direta das cores dos
quadrados, seja por um modelo de deep learning treinado para
classificá-los.

O TensorFlow só é importado sob demanda (veja `_get_model`), para que
estratégias que não usam deep learning (`PlayOnTerminal`,
`PlayOnWebsite`) não paguem o custo de inicializar o TensorFlow nem
exijam a presença do arquivo "modelo.keras".
"""
import os
import time

import cv2
import numpy as np
from playwright.sync_api import Page

# Tamanho de entrada esperado pelo modelo -- precisa ser exatamente o
# mesmo usado para treiná-lo (img_height/img_width em model.ipynb).
# Reduzido de 61x61 para 32x32: a rede só precisa identificar a cor de
# fundo predominante do quadrado, não a letra, então uma resolução bem
# menor já basta e deixa o pré-processamento e a inferência mais rápidos.
MODEL_INPUT_SIZE = (32, 32)

_MODEL = None  # Cache do modelo carregado (padrão Lazy Initialization).
_PREDICT_FN = None  # Cache da função de inferência compilada (tf.function).


def _get_model():
    """
    Carrega o modelo de deep learning usado por `predict_square`.

    O carregamento acontece apenas uma vez: na primeira chamada, o
    TensorFlow é importado, as variáveis de ambiente que silenciam
    seus logs são definidas e o modelo é lido de "modelo.keras". Nas
    chamadas seguintes, a instância já carregada é reaproveitada.

    Returns
    -------
    tensorflow.keras.Model
        Modelo treinado para classificar os quadrados do tabuleiro.
    """
    global _MODEL
    if _MODEL is None:
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
        import tensorflow as tf

        _MODEL = tf.keras.models.load_model("modelo.keras")
    return _MODEL


def _get_predict_fn():
    """
    Compila (uma única vez) a função usada para prever a cor dos
    quadrados a cada linha.

    `model.predict(...)` monta por baixo dos panos um pipeline de
    `tf.data.Dataset` a cada chamada, o que é ótimo para prever um
    dataset inteiro de uma vez, mas desproporcionalmente lento quando
    chamado repetidamente com lotes minúsculos -- exatamente o caso
    aqui, onde `predict_square` é chamada uma vez por linha (até 6
    vezes por partida). Envolver uma chamada direta ao modelo em
    `tf.function` compila o grafo uma única vez (na primeira linha) e
    reaproveita essa compilação nas linhas seguintes, já que o formato
    do lote de entrada (5 quadrados) nunca muda.

    Returns
    -------
    Callable
        Função que recebe um lote de imagens e devolve as previsões
        (logits) do modelo.
    """
    global _PREDICT_FN
    if _PREDICT_FN is None:
        import tensorflow as tf

        model = _get_model()

        @tf.function
        def _predict(batch):
            return model(batch, training=False)

        _PREDICT_FN = _predict
    return _PREDICT_FN


def type_word(page: Page, word: str) -> None:
    """
    Digita uma palavra no jogo e confirma o envio.

    Um pequeno atraso é utilizado entre cada tecla para tornar
    a digitação mais confiável durante a automação.

    Parameters
    ----------
    page : Page
        Página do navegador controlada pelo Playwright.

    word : str
        Palavra de cinco letras que será digitada.

    Returns
    -------
    None
    """
    for l in word:
        time.sleep(0.10)
        page.keyboard.type(l)
    page.keyboard.press("Enter")


def predict_square(squares) -> list:
    """
    Classifica os cinco quadrados de uma linha usando o modelo de
    deep learning.

    Cada quadrado é redimensionado para o tamanho esperado pelo modelo
    (`MODEL_INPUT_SIZE`) usando interpolação de área -- mais adequada
    para reduzir imagens do que o padrão do OpenCV, pois evita
    aliasing -- e convertido de BGR (padrão do OpenCV) para RGB antes
    de ser enviado à rede, que devolve a classe mais provável para
    cada posição.

    Parameters
    ----------
    squares : tuple[np.ndarray] or list[np.ndarray]
        Imagens dos cinco quadrados de uma linha do tabuleiro,
        conforme retornado por `print_row`.

    Returns
    -------
    list[int]
        Resultado previsto para cada posição:
            2 -> letra correta na posição correta (verde).
            1 -> letra presente em outra posição (amarelo).
            0 -> letra inexistente (preto).
    """
    class_values = [1, 0, 2]
    imgs = []

    for square in squares:
        square = cv2.resize(square, MODEL_INPUT_SIZE, interpolation=cv2.INTER_AREA)
        square = cv2.cvtColor(square, cv2.COLOR_BGR2RGB)
        imgs.append(square)

    imgs = np.array(imgs, dtype="float32")  # (5, H, W, 3)
    predict_fn = _get_predict_fn()
    preds = predict_fn(imgs).numpy()

    values = [class_values[np.argmax(p)] for p in preds]
    return values


def print_row(page: Page, row: int) -> tuple:
    """
    Captura uma linha do tabuleiro e separa seus cinco quadrados.

    A função realiza uma captura de tela da página, recorta a linha
    correspondente à tentativa informada e devolve uma imagem para
    cada uma das cinco posições.

    Parameters
    ----------
    page : Page
        Página do navegador.

    row : int
        Índice da linha (0 a 5).

    Returns
    -------
    tuple[np.ndarray]
        Tupla contendo as cinco imagens correspondentes aos quadrados
        da linha.
    """
    x1 = 483
    x2 = 796
    y1 = 125
    height = 60
    page.screenshot(path="termo.png")
    img = cv2.imread("termo.png")
    y2 = y1 + (row * 63)
    row_crop = img[y2:y2 + height, x1:x2]
    squares_list = []
    for i in range(5):
        squares_list.append(row_crop[0:0 + 60, 0 + (63 * i):0 + 60 + (63 * i)])
    return tuple(squares_list)


def check_collors(squares: tuple) -> list:
    """
    Determina o resultado de uma tentativa analisando as cores dos
    quadrados do tabuleiro.

    Para cada quadrado, identifica a cor predominante e converte para
    o mesmo formato utilizado pela lógica do jogo:

        2 -> letra correta na posição correta (verde)
        1 -> letra presente em outra posição (amarelo)
        0 -> letra inexistente (preto)

    Parameters
    ----------
    squares : tuple[np.ndarray]
        Tupla contendo as imagens dos cinco quadrados da tentativa.

    Returns
    -------
    list[int]
        Lista com o resultado correspondente a cada posição.
    """
    values = []
    for i, square in enumerate(squares):
        pixels = square.reshape(-1, 3)
        colors, count = np.unique(pixels, axis=0, return_counts=True)
        color = colors[np.argmax(count)]
        match list(color):
            case [105, 173, 211]:
                values.append(1)
            case [44, 42, 49]:
                values.append(0)
            case [148, 163, 58]:
                values.append(2)
    return values
