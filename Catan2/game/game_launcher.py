from Catan2.game.game import CatanGame

def start_game_process(client, username, game_code, parent_window):
    game = CatanGame(client, username, game_code, parent_window)
    result = game.run()

    if result == "go_to_lobby":
        parent_window.center_stack.setCurrentIndex(
            parent_window.page_indices["Home"]
        )
        parent_window.on_nav_clicked("Home")
        parent_window.show()
