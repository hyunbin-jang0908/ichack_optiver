import logging
import time
from typing import List
from optibook import common_types as t
from optibook import ORDER_TYPE_IOC, ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
import json

logging.getLogger('client').setLevel('ERROR')
logger = logging.getLogger(__name__)

INSTRUMENT_ID = 'SMALL_CHIPS'
INSTRUMENT_IDS = ['SMALL_CHIPS', 'TECH_INC', 'SMALL_CHIPS_NEW_COUNTRY', 'TECH_INC_NEW_COUNTRY']
SMALL_CHIPS_IDS = ['SMALL_CHIPS_NEW_COUNTRY']
TECH_INC_IDS = ['TECH_INC_NEW_COUNTRY']


class OrderStatusEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, t.OrderStatus):
            return str(obj)
        return super().default(obj)

def print_report(e: Exchange):
    pnl = e.get_pnl()
    positions = e.get_positions()
    my_trades = e.poll_new_trades(INSTRUMENT_ID)
    all_market_trades = e.poll_new_trade_ticks(INSTRUMENT_ID)
    logger.info(f'I have done {len(my_trades)} trade(s) in {INSTRUMENT_ID} since the last report. There have been {len(all_market_trades)} market trade(s) in total in {INSTRUMENT_ID} since the last report.')
    logger.info(f'My PNL is: {pnl:.2f}')
    logger.info(f'My current positions are: {json.dumps(positions, indent=3)}')
    logger.info("orders: " + json.dumps(e.get_outstanding_orders(INSTRUMENT_ID), cls=OrderStatusEncoder))

def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logger.info(f"Inserted order successfully, order_id='{order_response.order_id}'")
    else:
        logger.info(f"Unable to insert order with reason: '{order_response.success}'")


def trade_cycle(e: Exchange, ids, min_selling, max_buying):
    # this is the main bot logic which gets called every 5 seconds
    # fetch the current order book

    for instrument_id in ids:
        tradable_instruments = e.get_instruments()

        # first we verify that the instrument we wish to trade actually exists
        if instrument_id not in tradable_instruments:
            logger.info(f"Unable to trade because instrument '{instrument_id}' does not exist")
            continue

        # then we make sure that the instrument is not currently paused
        if tradable_instruments[instrument_id].paused:
            logger.info(f"Skipping cycle because instrument '{instrument_id}' is paused, will try again in the next cycle.")
            continue

        # Get the latest order book
        book = e.get_last_price_book(instrument_id)

        # verify that the book exists and that it has at least one bid and ask
        if book and book.bids and book.asks:
            # Calculate the spread and mid price
            spread = book.asks[0].price - book.bids[0].price
            mid_price = (book.asks[0].price + book.bids[0].price) / 2

            if e.get_positions()[instrument_id] < -100:
                bid_price = book.bids[0].price - 0.2
                response: InsertOrderResponse = e.insert_order(instrument_id, price=bid_price, volume=20, side=SIDE_BID, order_type=ORDER_TYPE_LIMIT)
                print_order_response(response)

            elif e.get_positions()[instrument_id] > 100:
                ask_price = book.asks[0].price - 0.1
                response: InsertOrderResponse = e.insert_order(instrument_id, price=ask_price, volume=10, side=SIDE_ASK, order_type=ORDER_TYPE_LIMIT)
                print_order_response(response)

            # If the spread is wide enough, place orders to try and capture the spread
            elif book.bids[0].price > min_selling and (e.get_positions()[instrument_id]) >= -90:
                # Place an ask order at the best ask price
                ask_price = book.asks[0].price
                response: InsertOrderResponse = e.insert_order(instrument_id, price=ask_price, volume=20, side=SIDE_ASK, order_type=ORDER_TYPE_LIMIT)
                print_order_response(response)

            elif book.bids[0].price <= max_buying and (e.get_positions()[instrument_id]) <= 90:
                # Place an ask order slightly below the best bid price
                bid_price = book.bids[0].price - 0.05
                response: InsertOrderResponse = e.insert_order(instrument_id, price=bid_price, volume=10, side=SIDE_BID, order_type=ORDER_TYPE_LIMIT)
                print_order_response(response)
            
        else:
            logger.info(f"No top bid/ask or no book at all for the instrument '{instrument_id}'")

        print_report(e)


def main():
    exchange = Exchange()
    exchange.connect()

    # you can also define host/user/pass yourself
    # when not defined, it is taken from ~/.optibook file if it exists
    # if that file does not exists, an error is thrown
    #exchange = Exchange(host='host-to-connect-to', info_port=7001, exec_port=8001, username='your-username', password='your-password')
    #exchange.connect()

    sleep_duration_sec = 2
    while True:
        trade_cycle(exchange, SMALL_CHIPS_IDS, 132.5, 131.5)
        trade_cycle(exchange, TECH_INC_IDS, 273.8, 273.4)
        logger.info(f'Iteration complete. Sleeping for {sleep_duration_sec} seconds')
        time.sleep(sleep_duration_sec)


if __name__ == '__main__':  
    main()
