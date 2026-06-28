import time
import cv2
import numpy as np
from playwright.sync_api import Page

AZUL = (58,163,148)
AMARELO = (211,173,105)
PRETO = (49,42,44)
X1 = 483
X2 = 796
Y = 125
ALTURA = 60

def main():
    ...
def type_word(page:Page,word) -> None:
    for l in word:
        time.sleep(0.20)
        page.keyboard.type(l)
    page.keyboard.press("Enter")


def print_row(page:Page,row:int) -> tuple:
    page.screenshot(path="termo.png")
    img = cv2.imread("termo.png")
    y = Y + (row * 63)
    recorte_fila = img[y:y+ALTURA,X1:X2]
    quadrados_lista = []
    for i in range(5):
        quadrados_lista.append(recorte_fila[0:0 + 60, 0 + (63 * i):0 + 60 + (63 * i)])
    return tuple(quadrados_lista)

def check_collors(squares:tuple) -> list:
    values = []
    for i,square in enumerate(squares):
        pixels = square.reshape(-1,3)
        cores,contagem = np.unique(pixels, axis=0, return_counts=True)
        cor = cores[np.argmax(contagem)]
        match cor:
            case [105, 173, 211]:
                values.append(1)
            case [44, 42, 49]:
                values.append(0)
            case [148, 163, 58]:
                values.append(2)
    return values

if __name__ == "__main__":
    main()