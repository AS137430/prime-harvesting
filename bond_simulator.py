import numpy
import pandas

# How to make it work monthly?
# gen_payments need to be monthly instead of annual
# numpy.py in value() needs to use maturity/12
# does bootstrap need to be reworked?
# need to use the a2m to get a monthly yield
# what if we just create the bond with a "monthly" yield instead of annual?
#   does everything magically work if we do that?

def iterate_fund(ladder, yield_curve, max_maturity):
    ladder.reduce_maturities()
    ladder.generate_payments()
    sold_bonds = ladder.sell_bonds(yield_curve)

    # Only buy a new bond if we actually sold one...
    if sold_bonds:
        ladder.buy_bond(yield_curve[max_maturity-1], max_maturity)
    
    # This happens *after* we sell the shortest bond and buy a new long one
    # (at least, that's what longinvest does...)
    nav = ladder.get_nav(yield_curve)

    return (ladder, nav)

def a2m(annual_rate):
    return pow(annual_rate + 1, 1/12) - 1

class Bond:
    def __init__(self, face_value, yield_pct, maturity):
        self.face_value = face_value
        self.yield_pct = yield_pct
        self.maturity = maturity
        
    def __repr__(self):
        return ('Maturity: %d | Yield: %.2f%% | Face Value: $%.2f' % (self.maturity, self.yield_pct * 100, self.face_value))

    def gen_payment(self):
        return self.face_value * self.yield_pct
    
    def value(self, rates):
        value = numpy.pv(rates[self.maturity - 1], self.maturity, (self.face_value * self.yield_pct), self.face_value)
        return -value
    
class BondLadder:
    def __init__(self, min_maturity, max_maturity):
        self.min_maturity = min_maturity
        self.max_maturity = max_maturity
        self.cash = 0
        
        self.ladder = set()
        
    def print_all(self):
        for bond in sorted(self.ladder, key=lambda b: b.maturity):
            print(bond)
            
    def print_all_values(self, rates):
        for bond in sorted(self.ladder, key=lambda b: b.maturity):
            print(bond.value(rates))
        
    def buy_bond(self, rate, maturity):
        b = Bond(self.cash, rate, maturity)
        self.add_bond(b)
        self.cash = 0
        return b
        
    def get_nav(self, rates):
        return self.cash + sum((b.value(rates) for b in self.ladder))

    def generate_payments(self):
        self.cash += sum((b.gen_payment() for b in self.ladder))        
        
    def __repr__(self):
        return ('%d-%d Ladder { Num Bonds: %d. }' % (self.max_maturity, self.min_maturity, len(self.ladder)))
        
    def add_bond(self, bond):
        #assert bond.maturity <= self.max_maturity
        #assert bond.maturity >= self.min_maturity
        self.ladder.add(bond)
    
    def reduce_maturities(self):
        for bond in self.ladder:
            bond.maturity -= 1

    def sell_bonds(self, rates):
        to_sell = filter(lambda bond: bond.maturity < self.min_maturity, self.ladder)
        to_sell = list(to_sell)
        self.ladder = self.ladder.difference(to_sell)
        self.cash += sum((b.value(rates) for b in to_sell))
        return to_sell

def bootstrap(yield_curve, max_bonds, min_maturity):
    ladder = BondLadder(min_maturity, max_bonds)
    starting_face_value = 50 # chosen arbitrarily (to match longinvest)

    for j in range(min_maturity, max_bonds+1):
        bond_yield = yield_curve[max_bonds-1]
        face_value = pow(1 + bond_yield, j-min_maturity) * starting_face_value
        b = Bond(face_value, bond_yield, j)
        ladder.add_bond(b)
    return ladder

def loop(ladder, rates, max_maturity):
    df = pandas.DataFrame(columns=['NAV', 'Change'])

    # The first iterations have fake data with duplicate years
    # But that's okay because we overwrite them with later data
    # (since they all have the same year)
    for (year, current_rates) in rates:
#        if year.year % 5 == 0 and year.month == 1:
#            print('Calculating...', year.year)
        (ladder, nav) = iterate_fund(ladder, current_rates.tolist(), max_maturity)
        df.loc[year] = {'NAV' : nav, 'Change' : None}

    calculate_returns(df)
    return df

def calculate_returns(df):
    change = df / df.shift(1) - 1
    df['Change'] = change.shift(-1)
    return df

def make_annual_ladder(max_maturity, min_maturity, yields):
    rate = yields[max_maturity - 1]
    
    # We have to add the "- 12" in order to make things like up with how
    # longinvest runs things. His "10-4" ladder is really more of "10-3" ladder:
    # bonds get sold the moment they become a 3 year bond.
    ladder = BondLadder(min_maturity - 12, max_maturity)

    face_value = 50
    for i in range(min_maturity, max_maturity + 1, 12):
        ladder.add_bond(Bond(face_value, rate, i))
        face_value = face_value * (1 + rate)

    return ladder

def simulate_turnover(max_maturity, min_maturity, rates):
    """
    rate is expected to be a pandas dataframe with one column per year
    up to max maturity columns (10 years == 10 columns)
    """
    initial_yields = rates.iloc[0].tolist()
    yields = rates.iterrows()
    #initial_yields = rates['1970'].values.tolist()[0]
    #yields = rates['1970':].iterrows()
    ladder = bootstrap(initial_yields, max_maturity, min_maturity)
    return loop(ladder, yields, max_maturity)
