import time
import cv2
from playwright.sync_api import sync_playwright

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
        imagem = cv2.imread("termo.png")
        recorte = imagem[128:180,486:796]
        cv2.imshow("recorte",recorte)
        cv2.waitKey(0)
        input("Pressione Enter...")

def type_word(page,word="serao"):
    for l in word:
        time.sleep(0.25)
        page.keyboard.type(l)
    page.keyboard.press("Enter")

if __name__ == "__main__":
    main()