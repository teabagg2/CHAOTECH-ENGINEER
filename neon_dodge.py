
import tkinter as tk
import random
import time

W, H = 600, 700
root = tk.Tk()
root.title("NEON DODGE")
root.resizable(False, False)
c = tk.Canvas(root, width=W, height=H, bg="#090d1f",
              highlightthickness=0)
c.pack()

c.create_text(300, 35, text="NEON DODGE", fill="#00f5ff",
              font=("Arial", 24, "bold"))
score_label = c.create_text(18, 72, anchor="w",
                            text="Score: 0", fill="white",
                            font=("Arial", 14))
c.create_text(300, 680, text="Move: WASD / ARROWS | R: Restart",
              fill="#7b86a8", font=("Arial", 10))

px, py = 300, 590
player = c.create_rectangle(px-17, py-17, px+17, py+17,
                            fill="#00f5ff", outline="white")
message = c.create_text(300, 350, text="Press SPACE to start",
                        fill="white", font=("Arial", 23, "bold"))
keys, enemies = set(), []
score, active, over = 0, False, False
last_spawn = 0

def key_down(e):
    global active
    k = e.keysym.lower()
    keys.add(k)
    if k == "space" and not active:
        reset()
    elif k == "r":
        reset()

def key_up(e):
    keys.discard(e.keysym.lower())

def reset():
    global px, py, score, active, over, last_spawn
    for enemy in enemies:
        c.delete(enemy[0])
    enemies.clear()
    px, py, score = 300, 590, 0
    active, over = True, False
    last_spawn = time.time()
    c.coords(player, px-17, py-17, px+17, py+17)
    c.itemconfig(score_label, text="Score: 0")
    c.itemconfig(message, text="")
    tick()

def tick():
    global px, py, score, over, last_spawn
    if not active or over:
        return

    speed = 6
    if "left" in keys or "a" in keys:
        px -= speed
    if "right" in keys or "d" in keys:
        px += speed
    if "up" in keys or "w" in keys:
        py -= speed
    if "down" in keys or "s" in keys:
        py += speed

    px = max(18, min(W-18, px))
    py = max(100, min(H-40, py))
    c.coords(player, px-17, py-17, px+17, py+17)

    now = time.time()
    if now - last_spawn > max(0.25, 0.8-score*0.008):
        x = random.randint(20, W-20)
        color = random.choice(["#ff2e88", "#ffb000", "#a855f7"])
        item = c.create_oval(x-14, -30, x+14, -2,
                             fill=color, outline="")
        enemies.append([item, x, -16,
                        random.uniform(3, 6)+score*0.03])
        last_spawn = now

    for enemy in enemies[:]:
        item, x, y, velocity = enemy
        y += velocity
        enemy[2] = y
        c.coords(item, x-14, y-14, x+14, y+14)

        if abs(x-px) < 29 and abs(y-py) < 29:
            over = True
            c.itemconfig(message, text=f"GAME OVER\nScore: {score}\nPress R to retry")
            return

        if y > H+20:
            c.delete(item)
            enemies.remove(enemy)
            score += 1
            c.itemconfig(score_label, text=f"Score: {score}")

    root.after(16, tick)

root.bind("<KeyPress>", key_down)
root.bind("<KeyRelease>", key_up)
root.mainloop()
