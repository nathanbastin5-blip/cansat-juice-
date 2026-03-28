"""Transmitter BMP280, TMP36, RFM69, SGP30"""

# ===========================================================================================================================================================
import math
import time

from adafruit_sgp30 import Adafruit_SGP30
from bme280 import BME280, BMP280_I2CADDR
from machine import I2C, PWM, SPI, Pin
from rfm69 import RFM69

# --- CONSTANTES ---
SEA_LEVEL_PRESSURE = 1013.25  # Pression moyenne au niveau de la mer en hPa

# ===========================================================================================================================================================
# Adresse I2C par défaut du MPU6050
MPU6050_I2C_ADDR = 0x68
# Registres du MPU6050
MPU6050_PWR_MGMT_1 = 0x6B
MPU6050_ACCEL_XOUT_H = 0x3B
MPU6050_GYRO_XOUT_H = 0x43
# Constantes pour la conversion
ACCEL_SCALE_MODIFIER = 16384.0  # 1 g = 16384 valeurs brutes
GYRO_SCALE_MODIFIER = 131.0  # 1 °/s = 131 valeurs brutes
# ===========================================================================================================================================================
NAME = "Python"
FREQ = 433.1

ENCRYPTION_KEY = b"\x01\x02\x03\x04\x05\x06\x07\x08\x01\x02\x03\x04\x05\x06\x07\x08"
NODE_ID = 120  # ID of this node
BASESTATION_ID = 100  # ID of the node (base station) to be contacted
# ============================================================================================================================================================
# ============================================================================================================================================================
# Buses & Pins
ventilateur = PWM(Pin(16, mode=Pin.OUT))
ventilateur.freq(1000)
em = Pin(13, mode=Pin.OUT)
em.on()

spi = SPI(
    0,
    sck=Pin(6),
    mosi=Pin(7),
    miso=Pin(4),
    baudrate=50000,
    polarity=0,
    phase=0,
    firstbit=SPI.MSB,
)
#####teste changement de pin############nss = Pin(5, Pin.OUT, value=True)
nss = Pin(17, Pin.OUT, value=True)
rst = Pin(3, Pin.OUT, value=False)

i2c = I2C(0, scl=Pin(9), sda=Pin(8))  # initialize the i2c bus on GP9 and GP8
i2cCO2 = I2C(1, sda=Pin(10), scl=Pin(11), freq=100000)
# RFM Module
rfm = RFM69(spi=spi, nss=nss, reset=rst)
rfm.frequency_mhz = FREQ
rfm.encryption_key = ENCRYPTION_KEY
rfm.node = NODE_ID  # This instance is the node 120
rfm.destination = BASESTATION_ID  # Send to specific node 100

print("I2C devices:", i2c.scan())  # JLO
time.sleep(1)  # JLO

bmp = BME280(i2c=i2c, address=0x76)  # create a bmp object
# JLO attention : suite à la connection SDO -> GND , CS -> 3.3V, il semble que 0x77 soit devenu 0x76
# bmp = BME280(i2c=i2c, address=BMP280_I2CADDR) # create a bmp object
led = Pin(25, Pin.OUT)  # Onboard LED


# ==========================================
# INITIALISATION DU CAPTEUR SGP30
# ==========================================
print("Recherche du SGP30...")
try:
    sgp = Adafruit_SGP30(i2cCO2)
    print("✅ SGP30 détecté !")
    print("Numéro de série :", [hex(i) for i in sgp.serial])
except Exception as e:
    print("❌ Erreur d'initialisation :", e)
    exit()

# ==========================================
# PHASE DE PRÉCHAUFFAGE (15 secondes)
# ==========================================
# Le SGP30 a besoin de temps pour stabiliser sa plaque chauffante
print("Démarrage du préchauffage (15s)...")
start_time = time.time()

while time.time() - start_time < 15:
    # On lit quand même pour maintenir l'algorithme interne
    co2 = sgp.co2eq
    voc = sgp.tvoc
    remaining = 15 - int(time.time() - start_time)
    print(
        f"Préchauffage... {remaining}s restantes (Valeurs : {co2}ppm / {voc}ppb)",
        end="\r",
    )
    time.sleep(1)

print("\n\n✅ Préchauffage terminé. Mesures en direct :\n")


# Fonction pour initialiser le MPU6050
def init_mpu6050():
    # Réveiller le MPU6050 (quitter le mode veille)
    i2c.writeto_mem(MPU6050_I2C_ADDR, MPU6050_PWR_MGMT_1, b"\x00")
    print("MPU6050 initialisé avec succès.")


# Fonction pour lire des registres sur 2 octets (valeur brute)
def read_raw_data(addr):
    high = i2c.readfrom_mem(MPU6050_I2C_ADDR, addr, 1)[0]
    low = i2c.readfrom_mem(MPU6050_I2C_ADDR, addr + 1, 1)[0]
    value = (high << 8) | low
    if value > 32767:  # Gérer les valeurs négatives
        value -= 65536
    return value


# Fonction pour lire les données de l'accéléromètre et les convertir en g
def read_accel_data():
    accel_x = read_raw_data(MPU6050_ACCEL_XOUT_H) / ACCEL_SCALE_MODIFIER
    accel_y = read_raw_data(MPU6050_ACCEL_XOUT_H + 2) / ACCEL_SCALE_MODIFIER
    accel_z = read_raw_data(MPU6050_ACCEL_XOUT_H + 4) / ACCEL_SCALE_MODIFIER
    return accel_x, accel_y, accel_z


# Fonction pour lire les données du gyroscope et les convertir en °/s
def read_gyro_data():
    gyro_x = read_raw_data(MPU6050_GYRO_XOUT_H) / GYRO_SCALE_MODIFIER
    gyro_y = read_raw_data(MPU6050_GYRO_XOUT_H + 2) / GYRO_SCALE_MODIFIER
    gyro_z = read_raw_data(MPU6050_GYRO_XOUT_H + 4) / GYRO_SCALE_MODIFIER
    return gyro_x, gyro_y, gyro_z


# Initialisation du MPU6050
init_mpu6050()

# Calibrage initial (valeurs moyennes au repos)
print("Calibrage en cours...")
calib_accel_x, calib_accel_y, calib_accel_z = 0, 0, 0
calib_gyro_x, calib_gyro_y, calib_gyro_z = 0, 0, 0
num_samples = 100

for _ in range(num_samples):
    ax, ay, az = read_accel_data()
    gx, gy, gz = read_gyro_data()
    calib_accel_x += ax
    calib_accel_y += ay
    calib_accel_z += az
    calib_gyro_x += gx
    calib_gyro_y += gy
    calib_gyro_z += gz
    time.sleep(0.01)

calib_accel_x = calib_accel_x / num_samples
calib_accel_y /= num_samples
calib_accel_z = (calib_accel_z / num_samples) - 1.0  # Retirer 1 g pour Z (gravité)
calib_gyro_x /= num_samples
calib_gyro_y /= num_samples
calib_gyro_z /= num_samples

print(
    f"Calibrage terminé : Accélération (X={calib_accel_x}, Y={calib_accel_y}, Z={calib_accel_z})"
)
print(f"Gyroscope (X={calib_gyro_x}, Y={calib_gyro_y}, Z={calib_gyro_z})")
# ===========================================
# Main Loop
# ===========================================
print("Frequency     :", rfm.frequency_mhz)
print("encryption    :", rfm.encryption_key)
print("NODE_ID       :", NODE_ID)
print("BASESTATION_ID:", BASESTATION_ID)

print("iteration_count, time_sec, pressure_hpa, bmp280_temp")  # print header
debut = time.time()  # time now


def moyenne(donnees: list) -> float:
    return sum(donnees) / len(donnees)


def est_en_train_de_descendre(altitudes: list, tolerance_m=5):
    """
    Détermine si on est en train de descendre. On dit qu'on descend si l'altitude moyenne des quatre dernières mesures (il y a ≃1s) sont "tolérance" mètres plus bas que l'altitude moyenne lors des 8 à 5 dernières mesures (il y a ≃2s).
    """
    if len(altitudes) < 10:
        return False
    # Altitude moyenne dans la dernière seconde
    altitude_maintenant = moyenne(
        [altitudes[-1], altitudes[-2], altitudes[-3], altitudes[-4]]
    )
    altitude_2s = moyenne([altitudes[-5], altitudes[-6], altitudes[-7], altitudes[-8]])
    # Si on est descendu d'au moins 5m, alors on est en train de descendre
    if altitude_maintenant < altitude_2s - tolerance_m:
        return True
    else:
        # Sinon, on ne descend pas
        return False


def activer_ventilateur():
    ventilateur.duty_u16(65535)


def desactiver_ventilateur():
    ventilateur.duty_u16(0)


def prendre_mesure_accel_gyro():
    # Lire les données de l'accéléromètre et du gyroscope
    accel_x, accel_y, accel_z = read_accel_data()
    gyro_x, gyro_y, gyro_z = read_gyro_data()
    # Appliquer le calibrage
    accel_x -= calib_accel_x
    accel_y -= calib_accel_y
    accel_z -= calib_accel_z
    gyro_x -= calib_gyro_x
    gyro_y -= calib_gyro_y
    gyro_z -= calib_gyro_z
    normG = math.sqrt(accel_x * accel_x + accel_y * accel_y + accel_z * accel_z)
    return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, normG


altitudes = []
fichier_donnees = open("donnes.csv", "w")
fichier_messages = open("messages.txt", "w")

while True:
    try:
        # Lecture des valeurs
        co2_val = sgp.co2eq
        voc_val = sgp.tvoc
        temp, pressure, humidity = (
            bmp.raw_values
        )  # read BMP280: Temp, pressure (hPa), humidity

        # 2. CALCUL DE L'ALTITUDE
        # Formule : 44330 * (1 - (P / P_mer)^(1/5.255))
        altitude = 44330 * (
            1.0 - math.pow(pressure / SEA_LEVEL_PRESSURE, (1.0 / 5.255))
        )
        altitudes.append(altitude)
        if est_en_train_de_descendre(altitudes):
            em.off()  # Désactiver les électro-aimants
            activer_ventilateur()  # Activer le ventilateur

        fichier_messages.write("-" * 30 + "\n")
        fichier_messages.write("Qualité de l'air :\n")
        fichier_messages.write(f"  eCO2 (Équivalent CO2) : {co2_val} ppm\n")
        fichier_messages.write(f"  TVOC (Composés Volatils) : {voc_val} ppb\n")
        fichier_messages.write(f"ALTITUDE : {altitude:.2f} m\n")

        accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, normG = (
            prendre_mesure_accel_gyro()
        )
        # Afficher les valeurs converties
        fichier_messages.write(
            f"Accéléromètre (g) : X={accel_x:.5f}, Y={accel_y:.5f}, Z={accel_z:.5f}, -> {normG:.5f}\n"
        )
        fichier_messages.write(
            f"Gyroscope (°/s) : X={gyro_x:.2f}, Y={gyro_y:.2f}, Z={gyro_z:.2f}\n"
        )
        fichier_messages.write("-" * 50 + "\n")

        msg = f"{time.time() - debut:.1},{humidity},{pressure:.2f},{temp:.1f},{altitude:.1f},{em.is_on()},{co2_val},{voc_val},{accel_x},{accel_y}, {accel_z},{gyro_x},{gyro_y},{gyro_z},{normG}"
        fichier_messages.write(msg + "\n")
        fichier_donnees.write(msg + "\n")
        led.on()  # Led ON while sending data
        # On envoie les données par bloc de 60 à la fois (de l'indice i inclus à i + 60 exclus)
        msg_bytes = bytes(msg, "utf-8")
        for i in range(0, len(msg_bytes), 60):
            rfm.send(msg_bytes[i : i + 60])
        led.off()
        time.sleep(0.25)  # wait before next reading
    except Exception:
        break

fichier_donnees.close()
fichier_messages.close()
