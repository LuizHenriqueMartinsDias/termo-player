import time
import cv2
from playwright.sync_api import sync_playwright
AZUL = (58,163,148)
AMARELO = (211,173,105)
PRETO = (49,42,44)
X1 = 483
X2 = 796
Y = 125
ALTURA = 52

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        page.goto("https://term.ooo/")

        page.keyboard.press("Escape")
        type_word(page)

        time.sleep(3)
        page.screenshot(path="termo.png")

        save_prints(page)
        input("Pressione Enter...")

def type_word(page,word="serao"):
    for l in word:
        time.sleep(0.25)
        page.keyboard.type(l)
    page.keyboard.press("Enter")

def save_prints(page):
    img = cv2.imread("termo.png")
    cv2.rectangle(
        img,
        (483, 125),  # canto superior esquerdo
        (483+61, 182),  # canto inferior direito
        (0, 0, 255),  # vermelho (BGR)
        2  # espessura da borda
    )
    cv2.imshow("Retangulo", img)
    cv2.waitKey(0)
    recorte = img[Y:Y+ALTURA,X1:X2]
    cv2.imshow("recorte", recorte)
    cv2.waitKey(0)

def check_collors(page) -> list:
    ...
if __name__ == "__main__":
    main()