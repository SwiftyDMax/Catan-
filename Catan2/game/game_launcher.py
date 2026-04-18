from Catan2.game.game import CatanGame

def start_game_process(client, username, game_code,parent_window):
    game = CatanGame(client, username, game_code,parent_window)
    game.run()