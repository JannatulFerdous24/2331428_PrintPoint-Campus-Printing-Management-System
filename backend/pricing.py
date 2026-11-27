"""
Printing cost (rates agreed with the print shop, in Bangladeshi Taka per printed page):

    Black & White  Tk 2 / page
    Color          Tk 10 / page

    total_cost = pages x copies x rate

The SERVER always calculates the cost - a price sent by the browser is never
trusted. The frontend shows an estimate using the same rates (GET /api/print-requests/pricing).
"""

from models import PrintType

CURRENCY = "BDT"
RATES_PER_PAGE: dict[PrintType, int] = {
    PrintType.black_and_white: 2,
    PrintType.color: 10,
}


def calculate_cost(pages: int, copies: int, print_type: PrintType) -> int:
    return pages * copies * RATES_PER_PAGE[print_type]
