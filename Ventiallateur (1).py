from machine import Pin, PWM
import time

# Configuration de la broche GP15
motor = PWM(Pin(16))
motor.freq(1000)

print("Test ON/OFF en boucle (Appuyez sur Ctrl+C pour arrêter)")

try:
    while True:
        # ALLUMER AU MAX (100%)
        print("Moteur : ON (Vitesse Max)")
        motor.duty_u16(65535) 
        time.sleep(4)
        
        # ÉTEINDRE (0%)
        print("Moteur : OFF")
        motor.duty_u16(0)
        time.sleep(2)

except KeyboardInterrupt:
    # Sécurité à l'arrêt
    motor.duty_u16(0)
    motor.deinit()
    print("Programme arrêté.")