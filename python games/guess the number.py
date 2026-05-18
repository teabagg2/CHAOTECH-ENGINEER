import random 
number = random.randint(1, 10)
print("Guess a number between 1 and 10")
while True:
    guess = int(input("Your guess: "))
    if guess == number:
        print("you win!")
        break
    elif guess < number:
        print("Too low, try again.")
    else:
        print("Too high, try again.")