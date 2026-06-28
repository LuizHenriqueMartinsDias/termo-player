import time
from pathlib import Path

import cv2
from playwright.sync_api import sync_playwright
AZUL = (58,163,148)
AMARELO = (211,173,105)
PRETO = (49,42,44)
X1 = 483
X2 = 796
Y = 125
ALTURA = 60

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        page.goto("https://term.ooo/")
        page.keyboard.press("Escape")
        row = -1
        row += type_word(page)
        time.sleep(2)
        print_row(page,row)
        row += type_word(page,word="abrir")
        time.sleep(2)
        print_row(page, row)
        row += type_word(page,word="horas")
        time.sleep(2)
        print_row(page, row)
        row += type_word(page,word="colar")
        time.sleep(2)
        print_row(page, row)
        row += type_word(page,word="urina")
        time.sleep(2)
        print_row(page, row)
        row += type_word(page,word="aguar")
        time.sleep(2)
        print_row(page, row)


        input("Pressione Enter...")

def type_word(page,word="serao"):
    for l in word:
        time.sleep(0.20)
        page.keyboard.type(l)
    page.keyboard.press("Enter")
    return 1

def print_row(page,row:int):
    page.screenshot(path="termo.png")
    img = cv2.imread("termo.png")
    y = Y + (row * 63)
    recorte_fila = img[y:y+ALTURA,X1:X2]
    cv2.imshow("recorte", recorte_fila)
    print = 0

    cv2.waitKey(0)
    for i in range(5):
        recorte_quadrado = recorte_fila[0:0+60,0 + (63*i):0 + 60 + (63*i)]
        cv2.imshow(f"recorte{i}", recorte_quadrado)
        cv2.waitKey(0)
        while Path(f"recorte{print}.png").exists():
            print+=1
        cv2.imwrite(f"recorte{print}.png", recorte_quadrado)
    cv2.destroyAllWindows()

def check_collors(page) -> list:
    ...

if __name__ == "__main__":
    main()