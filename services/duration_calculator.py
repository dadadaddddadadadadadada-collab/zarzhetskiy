class DurationCalculator:
    DEFAULT_WORDS_PER_MINUTE = 140

    @staticmethod
    def count_words(text: str) -> int:
        words = text.split()
        return len(words)

    @staticmethod
    def calculate_minutes(text: str, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE) -> float:
        word_count = DurationCalculator.count_words(text)

        if words_per_minute <= 0:
            words_per_minute = DurationCalculator.DEFAULT_WORDS_PER_MINUTE

        return word_count / words_per_minute

    @staticmethod
    def format_duration(minutes: float) -> str:
        total_seconds = int(minutes * 60)
        mins = total_seconds // 60
        seconds = total_seconds % 60

        return f"{mins} мин. {seconds} сек."