import time
import threading

from auctions.StrategyContext import StrategyContext


class AuctionEngine:
    def __init__(self, auction_manager, trader_address, strategy, number_of_recent_blocks, frequency):
        self.auction_manager = auction_manager
        self.trader_address = trader_address
        self.strategy = strategy
        self.frequency = frequency
        self.number_of_recent_blocks = number_of_recent_blocks
        self.active_auctionlets = []
        self.lock = threading.Lock()


    def start(self):
        self._bind_events()
        self._discover_recent_auctionlets()
        while True:
            for auctionlet_id in self.active_auctionlets[:]:
                self._process_auctionlet(auctionlet_id)
            time.sleep(self.frequency)

    def _discover_recent_auctionlets(self):
        if (self.number_of_recent_blocks is not None):
            self.auction_manager.discover_recent_auctionlets(self.number_of_recent_blocks, self._on_recovered_auctionlet)

    def _bind_events(self):
        self.auction_manager.on_new_auction(self._on_new_auctionlet)
        self.auction_manager.on_bid(self._on_bid)
        self.auction_manager.on_split(self._on_split)

    def _on_recovered_auctionlet(self, auctionlet_id):
        print(f"Found old auctionlet #{auctionlet_id}")
        self.active_auctionlets.append(auctionlet_id)
        self._process_auctionlet(auctionlet_id)

    def _on_new_auctionlet(self, auctionlet_id):
        print(f"Discovered new auctionlet #{auctionlet_id}")
        self.active_auctionlets.append(auctionlet_id)
        self._process_auctionlet(auctionlet_id)

    def _on_bid(self, auctionlet_id):
        if (auctionlet_id not in self.active_auctionlets):
            print(f"Discovered new bid on a previously unknown auctionlet #{auctionlet_id}")
            self.active_auctionlets.append(auctionlet_id)
        else:
            print(f"Discovered new bid on an existing auctionlet #{auctionlet_id}")
        self._process_auctionlet(auctionlet_id)

    def _on_split(self, base_id, new_id, split_id):
        print(f"Discovered a split of auctionlet #{base_id} into auctionlets #{new_id} and #{split_id}")
        self.active_auctionlets.append(split_id)
        self._process_auctionlet(new_id)
        self._process_auctionlet(split_id)

    def _process_auctionlet(self, auctionlet_id):
        with self.lock:
            auctionlet = self.auction_manager.get_auctionlet(auctionlet_id)
            if auctionlet is not None:
                self._print_auctionlet(auctionlet_id, auctionlet)
                result = self.strategy.perform(auctionlet, StrategyContext(self.auction_manager.address, self.trader_address))
                self._print_auctionlet_outcome(auctionlet_id, result.description)
                if result.forget:
                    try:
                        self.active_auctionlets.remove(auctionlet_id)
                    except:
                        print("Failed to remove") #TODO implement thread-safe lists
            else:
                try:
                    self.active_auctionlets.remove(auctionlet_id)
                except:
                    print("Failed to remove") #TODO implement thread-safe lists

    def _print_auctionlet(self, auctionlet_id, auctionlet):
        auction = auctionlet.get_auction()
        heading = f"Auctionlet #{auctionlet_id}:"
        padding = ' ' * len(heading)
        width = 23
        print(f"{heading} [   selling: {str(auctionlet.sell_amount).rjust(width)} {auction.selling.name()}] [     creator: {auction.creator}]")
        print(f"{padding} [ start_bid: {str(auction.start_bid).rjust(width)} {auction.buying.name()}] [  parameters: min_incr={auction.min_increase}, min_decr={auction.min_decrease}, ttl={auction.ttl}, reversed={auction.reversed}, is_expired={auctionlet.is_expired()}]")
        print(f"{padding} [  last_bid: {str(auctionlet.buy_amount).rjust(width)} {auction.buying.name()}] [ last_bidder: {auctionlet.last_bidder} (@ {auctionlet.last_bid_time})]" )

    def _print_auctionlet_outcome(self, auctionlet_id, result):
        heading = f"Auctionlet #{auctionlet_id}:"
        padding = ' ' * len(heading)
        print(f"{padding} [   outcome: {result}]")
        print("")