import random

enemy_hp = 10
while enemy_hp > 0:
    action = input("shoot or reload? ")

    if action == "shoot":
        damage = random.randint(1, 5)
        enemy_hp -= damage
        print (f"You hit the enemy for {damage} damage")
        print(f"Enemy HP: {max(enemy_hp,0)}")
    elif action == "reload":
        print("Reloaded!")
    else:
        print("Invalid action")

print("Enemy defeated!")
