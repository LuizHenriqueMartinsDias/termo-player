"""
Ponto de entrada do Solver de Termo.

Substitui a antiga interface de linha de comando (argparse) por um
menu interativo no terminal: o usuário escolhe o modo de jogo e
informa palavra inicial/palavra correta quando necessário, sem
precisar lembrar de flags.
"""
import random
from pathlib import Path

import pandas as pd
from pandas import DataFrame

from player import (
    WORD_LIST,
    Context,
    PlayOnTerminal,
    PlayOnWebsite,
    PlayOnWebsiteDeepLearning,
)

WORD_LENGTH = 5

# Registro (padrão Factory) que liga cada opção do menu à sua
# estratégia. Adicionar um novo modo de jogo no futuro significa
# apenas acrescentar uma linha aqui — o menu e o laço principal não
# precisam mudar.
STRATEGIES = {
    "1": {
        "label": "Jogar no terminal (simulação)",
        "cls": PlayOnTerminal,
        "correct_word_required": True,
    },
    "2": {
        "label": "Jogar no navegador (visão computacional)",
        "cls": PlayOnWebsite,
        "correct_word_required": False,
    },
    "3": {
        "label": "Jogar no navegador (deep learning)",
        "cls": PlayOnWebsiteDeepLearning,
        "correct_word_required": False,
    },
}
DATASET_OPTION = "4"
EXIT_OPTION = "5"

def validate_answer(answer:str)->bool:
    return answer in WORD_LIST["palavras"].values

def ask_word(prompt: str, required: bool, length: int = WORD_LENGTH) -> str | None:
    """
    Solicita uma palavra ao usuário pelo terminal, validando o
    tamanho quando algo é digitado.

    Parameters
    ----------
    prompt : str
        Mensagem exibida ao usuário.

    required : bool
        Se True, o campo não pode ficar em branco.

    length : int, optional
        Tamanho esperado da palavra (padrão 5, o tamanho das
        palavras do Termo).

    Returns
    -------
    str or None
        Palavra validada em minúsculas, ou None se o campo for
        opcional e o usuário não digitar nada.
    """
    while True:
        answer = input(prompt).strip().lower()
        if not answer:
            if not required:
                return None
            return random.choice(WORD_LIST["palavras"])
        if validate_answer(answer):
            return answer
        print(f"A palavra deve estar na lista de palavras válidas.\n")
        continue


def show_menu() -> None:
    """Exibe as opções disponíveis do menu principal."""
    print("\n=== Solver de Termo ===")
    for key, opcao in STRATEGIES.items():
        print(f"{key}. {opcao['label']}")
    print(f"{DATASET_OPTION}. Gerar dataset de partidas")
    print(f"{EXIT_OPTION}. Sair")


def run_strategy(opcao: dict) -> None:
    """
    Coleta os dados necessários pelo terminal e executa a estratégia
    escolhida no menu.

    Parameters
    ----------
    opcao : dict
        Entrada de `STRATEGIES` correspondente à escolha do usuário.
    """
    first_word = ask_word("Palavra inicial (Enter para automático): ", required=False)

    if opcao["correct_word_required"]:
        correct_word = ask_word("Palavra correta(Enter para automático): ", required=True)
    else:
        correct_word = ask_word(
            "Palavra correta (Enter para jogar ao vivo no site): ", required=False
        )

    context = Context(opcao["cls"]())
    attempts, guesses, win, word = context.play_strategy(
        first_word=first_word, correct_word=correct_word
    )

    resultado = "Vitória" if win else "Derrota"
    print(f"\n{resultado} em {attempts} tentativa(s). Chutes: {guesses}")


def run_dataset_generation() -> None:
    """
    Gera o dataset de partidas: joga (em modo simulado, no terminal)
    contra cada palavra da lista, sempre a partir da mesma palavra
    inicial, e salva o resultado de cada partida.
    """
    first_word = ask_word("Palavra inicial para o dataset (enter para aleatória): ", required=True)
    context = Context(PlayOnTerminal())
    total = len(WORD_LIST["palavras"])
    path = Path(__file__).resolve().parent.parent / "data" / f"dataset_{first_word}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame()
    for indice, word in enumerate(WORD_LIST["palavras"].values, start=1):
        attempts,guesses,win,correct_word = context.play_strategy(first_word=first_word, correct_word=word)
        df = save_dataset(attempts,guesses,win,correct_word,df)
        print(f"[{indice}/{total}] {word} processada.")
    df.to_csv(path,index=False)
    print("\nDataset gerado com sucesso!")


def save_dataset(attempts: int, guesses: tuple, win: bool, correct_word: str,df:DataFrame) -> DataFrame:
    """
    Registra o resultado de uma partida em "data/dataset_01.csv",
    evitando duplicar a mesma combinação de palavra correta e palavra
    inicial.

    Parameters
    ----------
    df: Dataframe
        dataset a ser salvo

    attempts : int
        Número de tentativas utilizadas na partida.

    guesses : tuple[str]
        Todos os chutes realizados durante a partida.

    win : bool
        Se a partida terminou em vitória.

    correct_word : str
        Palavra correta da partida.

    Returns
    -------
    """

    novo_registro = pd.DataFrame(data={
        "Palavra_correta": correct_word,
        "palavra_inicial": guesses[0],
        "N_de_tentativas": attempts,
        "Chutes": [guesses],
        "Vitoria": win,
    })
    df = pd.concat(objs=(df,novo_registro))
    df.drop_duplicates(subset=["Palavra_correta", "palavra_inicial"], keep='last')
    return df

def main() -> None:
    """Laço principal: exibe o menu e executa a opção escolhida até o
    usuário optar por sair."""
    while True:
        show_menu()
        choice = input("Escolha uma opção: ").strip()

        if choice in STRATEGIES:
            run_strategy(STRATEGIES[choice])
        elif choice == DATASET_OPTION:
            run_dataset_generation()
        elif choice == EXIT_OPTION:
            print("Até mais!")
            break
        else:
            print("Opção inválida, tente novamente.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
