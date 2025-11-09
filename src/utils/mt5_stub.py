# utils/mt5_stub.py
class MT5Stub:
    """Заглушка для MT5 при отсутствии терминала"""
    def __init__(self):
        self.connected = False

    def initialize(self):
        print("⚠️ MT5Stub: Симуляция подключения (терминал не найден).")
        self.connected = True
        return True

    def shutdown(self):
        print("⚠️ MT5Stub: Отключение (симуляция).")
        self.connected = False
        return True

    def copy_rates_range(self, *args, **kwargs):
        print("⚠️ MT5Stub: Возврат фиктивных данных.")
        return []
