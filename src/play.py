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

def validate_answer(answer: str) -> bool:
    """
    Verifica se `answer` é uma palavra válida do dicionário do Termo.

    Parameters
    ----------
    answer : str
        Palavra digitada pelo usuário (já normalizada em minúsculas).

    Returns
    -------
    bool
        True se `answer` está na lista de palavras válidas.
    """
    return answer in WORD_LIST["palavras"].values


def ask_word(prompt: str, required: bool) -> str | None:
    """
    Solicita uma palavra ao usuário pelo terminal, validando que ela
    pertence ao dicionário do Termo (`validate_answer`).

    Parameters
    ----------
    prompt : str
        Mensagem exibida ao usuário.

    required : bool
        Comportamento quando o campo é deixado em branco: se True,
        uma palavra aleatória do dicionário é escolhida
        automaticamente; se False, retorna None (cabe a quem chamou
        decidir o que isso significa -- por exemplo, jogar ao vivo
        contra a palavra do dia).

    Returns
    -------
    str or None
        Palavra validada em minúsculas, uma palavra aleatória (campo
        obrigatório deixado em branco), ou None (campo opcional
        deixado em branco).
    """
    while True:
        answer = input(prompt).strip().lower()
        if not answer:
            if not required:
                return None
            return random.choice(WORD_LIST["palavras"])
        if validate_answer(answer):
            return answer
        print("A palavra deve estar na lista de palavras válidas.\n")


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
    inicial, e salva o resultado em
    "data/dataset_{palavra_inicial}.csv" -- palavras iniciais
    diferentes geram arquivos separados. Se o arquivo já existir, os
    novos resultados são combinados com os existentes (sem duplicar
    a mesma combinação de palavra correta e palavra inicial). Os
    resultados são acumulados em memória e gravados em disco uma
    única vez ao final, não a cada partida.
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


def save_dataset(attempts: int, guesses: tuple, win: bool, correct_word: str, df: DataFrame) -> DataFrame:
    """
    Adiciona o resultado de uma partida a `df`, evitando duplicar a
    mesma combinação de palavra correta e palavra inicial.

    Não grava nada em disco -- só devolve o DataFrame atualizado;
    quem chama decide quando salvar (`run_dataset_generation` escreve
    o CSV uma única vez, depois de processar todas as palavras, em
    vez de reabrir e regravar o arquivo a cada partida).

    Parameters
    ----------
    attempts : int
        Número de tentativas utilizadas na partida.

    guesses : tuple[str]
        Todos os chutes realizados durante a partida.

    win : bool
        Se a partida terminou em vitória.

    correct_word : str
        Palavra correta da partida.

    df : DataFrame
        Dataset acumulado até aqui.

    Returns
    -------
    DataFrame
        `df` com o novo registro adicionado, sem duplicar a mesma
        combinação de palavra correta e palavra inicial (mantendo a
        ocorrência mais recente em caso de duplicata).
    """
    novo_registro = pd.DataFrame(data={
        "Palavra_correta": correct_word,
        "palavra_inicial": guesses[0],
        "N_de_tentativas": attempts,
        "Chutes": [guesses],
        "Vitoria": win,
    })
    df = pd.concat(objs=(df, novo_registro), ignore_index=True)
    df = df.drop_duplicates(subset=["Palavra_correta", "palavra_inicial"], keep="last")
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
