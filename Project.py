import threading
import time
import random
import sys
from typing import List, Optional

# --- Zmienne Globalne i Zasoby ---
NUM_PUMPS = 3  # Liczba dostępnych dystrybutorów
PUMPS_SEMAPHORE = threading.Semaphore(NUM_PUMPS) # Semafor ograniczający dostęp do dystrybutorów
CASHIER_LOCK = threading.Lock() # Blokada chroniąca dostęp do kasy
CASHIER_BUSY = False # Stan kasy (dla prostszej symulacji blokady)
VEHICLE_COUNT = 0 # Licznik pojazdów
PRINT_LOCK = threading.Lock() # Blokada do synchronizacji wyświetlania na konsoli

# Lista symulująca zajętość poszczególnych dystrybutorów
pump_status = [f"D{i+1}: Wolny" for i in range(NUM_PUMPS)]

def safe_print(*args, **kwargs):
    """Funkcja do bezpiecznego wyświetlania logów, by uniknąć pomieszania tekstu."""
    with PRINT_LOCK:
        print(*args, **kwargs)

# --- Klasy Zasobów i Wątków ---

class Pump:
    """Reprezentacja Dystrybutora - chroniony przez Semafor."""
    def __init__(self, id: int):
        self.id = id
        
    def tank(self, vehicle_id: int):
        """Symuluje proces tankowania."""
        safe_print(f"🚗 Pojazd {vehicle_id} tankuje na Dystrybutorze D{self.id}...")
        tank_time = random.uniform(3, 7)
        time.sleep(tank_time)
        safe_print(f"✅ Pojazd {vehicle_id} zakończył tankowanie (czas: {tank_time:.2f}s).")

class Cashier:
    """Reprezentacja Kasy - chroniony przez Blokadę Mutex."""
    def process_payment(self, vehicle_id: int):
        """Symuluje proces płatności."""
        global CASHIER_BUSY
        
        safe_print(f"💰 Pojazd {vehicle_id} czeka na kasę...")
        
        with CASHIER_LOCK: # SEKCJA KRYTYCZNA: Dostęp do kasy
            CASHIER_BUSY = True
            safe_print(f"💳 Pojazd {vehicle_id} płaci w kasie. Kasa zajęta...")
            
            payment_time = random.uniform(1, 3)
            time.sleep(payment_time)
            
            safe_print(f"🎉 Pojazd {vehicle_id} zapłacił i opuszcza stację (czas: {payment_time:.2f}s).")
            CASHIER_BUSY = False # Zwolnienie kasy

class Vehicle(threading.Thread):
    """Wątek Użytkowy: Symulacja Pojazdu."""
    def __init__(self, id: int, pumps: List[Pump], cashier: Cashier):
        super().__init__()
        self.id = id
        self.pumps = pumps
        self.cashier = cashier
        
    def run(self):
        safe_print(f"🚘 Pojazd {self.id} przybył na stację i czeka na dystrybutor...")

        # 1. Zdobądź dostęp do dystrybutora (Semafor)
        PUMPS_SEMAPHORE.acquire()
        
        # Znajdź wolny dystrybutor
        pump_id = -1
        for i in range(NUM_PUMPS):
            with PRINT_LOCK: # Synchronizacja dostępu do statusu
                if pump_status[i].endswith("Wolny"):
                    pump_status[i] = f"D{i+1}: Zajęty przez V{self.id}"
                    pump_id = i + 1
                    break
        
        # Symulacja Race Condition: Dwa wątki mogą wejść do tego bloku,
        # zanim pump_status zostanie zaktualizowany, jeśli nie użyjemy blokady (ale używamy PRINT_LOCK).
        # Użycie Semfora jest głównym mechanizmem kontroli.

        # 2. Tankowanie
        selected_pump = next((p for p in self.pumps if p.id == pump_id), None)
        if selected_pump:
            selected_pump.tank(self.id)
            
            # Zwolnij dystrybutor
            with PRINT_LOCK:
                pump_status[pump_id - 1] = f"D{pump_id}: Wolny (zwolniony przez V{self.id})"
            
            PUMPS_SEMAPHORE.release()
            
            # 3. Płatność
            self.cashier.process_payment(self.id)
            safe_print(f"👋 Pojazd {self.id} opuścił stację.")
        else:
             # Zdarzenie awaryjne - nie powinno się zdarzyć
             safe_print(f"❌ Błąd: Pojazd {self.id} nie znalazł dystrybutora po acquire!")
             PUMPS_SEMAPHORE.release()


class StationManager(threading.Thread):
    """Wątek Zarządzający/Monitorujący: Generuje pojazdy i wyświetla stan."""
    def __init__(self, pumps: List[Pump], cashier: Cashier, max_vehicles: int = 10):
        super().__init__()
        self.pumps = pumps
        self.cashier = cashier
        self.max_vehicles = max_vehicles
        self.running = True
        
    def run(self):
        global VEHICLE_COUNT
        vehicle_threads = []
        
        safe_print("\n--- ⛽ START SYMULACJI STACJI BENZYNOWEJ ---")

        while VEHICLE_COUNT < self.max_vehicles and self.running:
            # 1. Generuj nowy pojazd
            time.sleep(random.uniform(1, 3))
            VEHICLE_COUNT += 1
            vehicle = Vehicle(VEHICLE_COUNT, self.pumps, self.cashier)
            vehicle_threads.append(vehicle)
            vehicle.start()
            
            # 2. Wyświetlaj stan (monitorowanie)
            self.display_status()
            
        safe_print("\n--- Zatrzymywanie generatora pojazdów. Oczekiwanie na zakończenie wszystkich wątków... ---")
        
        # Oczekiwanie na zakończenie wątków pojazdów
        for t in vehicle_threads:
            t.join()
            
        safe_print("--- ✅ SYMULACJA ZAKOŃCZONA ---")


    def display_status(self):
        """Wyświetla aktualny stan stacji."""
        status_line = f"\n[STAN STACJI] | Kasa: {'Zajęta' if CASHIER_LOCK.locked() else 'Wolna'} | "
        status_line += " | ".join(pump_status)
        safe_print(status_line)
        
    def stop(self):
        self.running = False


# --- Główna funkcja wykonawcza ---

if __name__ == "__main__":
    # Inicjalizacja zasobów
    all_pumps = [Pump(i + 1) for i in range(NUM_PUMPS)]
    the_cashier = Cashier()
    
    # Uruchom Menedżera Stacji (Wątek Zarządzający)
    manager = StationManager(all_pumps, the_cashier, max_vehicles=10) # Symulacja 10 pojazdów
    manager.start()
    
    # Czekaj na zakończenie Menedżera (a on czeka na pojazdy)
    try:
        manager.join()
    except KeyboardInterrupt:
        safe_print("\nPrzerwanie symulacji przez użytkownika.")
        manager.stop()
        sys.exit(0)
