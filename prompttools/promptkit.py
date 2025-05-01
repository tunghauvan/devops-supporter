# Example using prompt_toolkit (requires installation: pip install prompt_toolkit)
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

# List of words to suggest
suggestions = ['list_instances', 'connect_instance', 'show_config', 'exit', 'help']
completer = WordCompleter(suggestions, ignore_case=True)

if __name__ == '__main__':
    print("Type a command (try typing 'l' or 'c' and press Tab):")
    while True:
        try:
            user_input = prompt('> ', completer=completer)
            print(f'You entered: {user_input}')
            if user_input.lower() == 'exit':
                break
            # Add logic here to handle the user_input command
        except EOFError:
            break # Exit on Ctrl+D
    print('Goodbye!')
