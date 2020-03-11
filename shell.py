import click
from colorama import init
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from __init__ import __version__
from core.client import TkrbClient, execute

init(autoreset=True)


class TkrbCLI(object):
    def __init__(self, tkrbclient):
        self.client = tkrbclient
        self.history = InMemoryHistory()
        self.prompt = PromptSession(history=self.history)

    def run_cli(self):
        print(f"版本：{__version__}")
        while True:
            try:
                command = self.prompt.prompt("AutoTkrb> ")
            except (EOFError, KeyboardInterrupt):
                break
            else:
                execute(self.client, command)
                print("")

        print("掰掰囉 :D")


@click.command()
@click.option("--account", prompt="帳號", required=True)
@click.option("--password", prompt="密碼", hide_input=True, required=True)
def cli(account, password):
    client = TkrbClient.create(account, password)

    if not client:
        return

    cli = TkrbCLI(client)
    cli.run_cli()


if __name__ == "__main__":
    cli()
