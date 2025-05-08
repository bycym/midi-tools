import pygame
pygame.init()
pygame.mixer.music.load("csharp_loop.mid")
pygame.mixer.music.play()

# Keep script alive while music plays
while pygame.mixer.music.get_busy():
    continue
