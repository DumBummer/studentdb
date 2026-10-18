from decimal import Decimal

def calculate_final_grade(scores):
    """Weighted percentage. Each score item needs score, max_score and percentage."""
    weighted = Decimal('0')
    weights = Decimal('0')
    for item in scores:
        maximum = Decimal(str(item['max_score']))
        weight = Decimal(str(item['percentage']))
        score = Decimal(str(item['score']))
        if maximum <= 0 or weight < 0:
            raise ValueError('Maximum score must be positive and weight cannot be negative.')
        weighted += (score / maximum * Decimal('100')) * weight
        weights += weight
    return (weighted / weights).quantize(Decimal('0.01')) if weights else Decimal('0.00')
