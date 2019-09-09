import click
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from client import ClientCreateFailException, TkrbClient, execute

__version__ = "0.0.36"


class TkrbCLI(object):
    def __init__(self, tkrbclient):
        self.client = tkrbclient
        self.history = InMemoryHistory()
        self.cli_session = PromptSession(history=self.history)

    def run_cli(self):
        print(f"版本：{__version__}")
        while True:
            try:
                command = self.cli_session.prompt("TkrbAuto> ")
                execute(self.client, command)
            except KeyboardInterrupt:
                break
            except EOFError:
                break

        print("掰掰囉 :D")


@click.command()
@click.option("--account", prompt="帳號", required=True)
@click.option("--password", prompt="密碼", hide_input=True, required=True)
def cli(account, password):
    try:
        client = TkrbClient.create(account, password)
        r = TkrbCLI(client)
        r.run_cli()
    except ClientCreateFailException as e:
        print(e)


if __name__ == "__main__":
    cli()
