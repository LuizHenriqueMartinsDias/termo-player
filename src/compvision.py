import time
import cv2
import numpy as np
from playwright.sync_api import Page

def type_word(page:Page,word:str) -> None:
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
        time.sleep(0.20)
        page.keyboard.type(l)
    page.keyboard.press("Enter")

def print_row(page:Page,row:int) -> tuple:
    """
        Captura uma linha do tabuleiro e separa seus cinco quadrados.

        O função realiza uma captura de tela da página, recorta a linha
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
    row_crop = img[y2:y2+height,x1:x2]
    squares_list = []
    for i in range(5):
        squares_list.append(row_crop[0:0 + 60, 0 + (63 * i):0 + 60 + (63 * i)])
    return tuple(squares_list)

def check_collors(squares:tuple) -> list:
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
    for i,square in enumerate(squares):
        pixels = square.reshape(-1,3)
        colors,count = np.unique(pixels, axis=0, return_counts=True)
        color = colors[np.argmax(count)]
        match list(color):
            case [105, 173, 211]:
                values.append(1)
            case [44, 42, 49]:
                values.append(0)
            case [148, 163, 58]:
                values.append(2)
    return values

