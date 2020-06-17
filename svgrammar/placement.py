import math
import random
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class Solver(object):
    def __init__( self, graph ):
        self.movable = set()
        self.fixed = set()
        self.relations = []
        self.graph = graph

        self.temperature = 0.0
        self.current = None
        self.current_penalty = None
        self.best = None
        self.best_penalty = None
        self.best_temperature = None

        self.primary_scale = 10.0
        self.secondary_scale = 1.0

        self.paths = {}
        self.penalties = []
        self.temps = []
        self.verbose = False
        
    def add_edge( self, e1, relation, e2 ):
        # e2 is considered fixed, e1 is variable
        # read the relation as "e1 is to <adjacent to the left side of> e2"
        self.movable.add( e1 )
        self.fixed.add( e2 )
        self.relations.append( (e1, relation, e2) )
        # TODO: this allows A->B and A->C without forcing an ordering
        # of B<->C, so they could overlap; is this OK?

    def bounding_box( self, n ):
        return self.graph.nodes[n]["drawn"].bounding_box
        
    def start( self ):
        self.fixed.difference_update( self.movable )
        positions = {}
        for m in self.movable:
            bb = self.bounding_box( m )
            positions[m] = (0.0, 0.0)
            self.paths[m] = []
        self.current = positions
        self.current_penalty = self.penalty( self.current )
        self.best = self.current
        self.best_penalty = self.current_penalty

        print( "Intial positions:", positions )
        print( "Initial penalty:", self.penalty( positions ) )
        self.temperature = self.initial_temperature()
        print( "Intial temperature:", self.temperature )
        self.best_temperature = self.temperature

    def boundary_in( self, n, positions ):
        bb = self.bounding_box( n )
        if n in self.movable:
            return (bb.x1 + positions[n][0],
                    bb.y1 + positions[n][1],
                    bb.x2 + positions[n][0],
                    bb.y2 + positions[n][1])
        else:
            return (bb.x1, bb.y1, bb.x2, bb.y2 )

    def overlap_in( self, a, b, positions ):
        # The overlap penalty is calculated as the distance required
        # to cause the boxes to no longer overlap; it's the minimum of
        # moving it up, right, left or down-- diagonally is never necessary
        # for rectangles.
        #
        # |-------------|
        # |             |
        # |      XX     |
        # |      XX     |
        # |------XX-----|
        #
        # Two aligned rectangles do not overlap when
        # ax2 < bx1 OR
        # ax1 > bx2 OR
        # ay2 < by1 OR
        # ay1 > by2
        # So we need the minimum value that makes one of those true.
        # ax2 - d < bx1   <=>     ax2 - bx1 < d
        # ax1 + d > bx2   <=>     d > bx2 - ax1
        # ay2 - d < by1   <=>     ay2 - by1 < d
        # ay1 + d > by2   <->     d > by2 - ay1
        ax1, ay1, ax2, ay2 = self.boundary_in( a, positions )
        bx1, by1, bx2, by2 = self.boundary_in( b, positions )
        
        d =  max( min( ax2 - bx1,
                       bx2 - ax1,
                       ay2 - by1,
                       by2 - ay1 ), 0.0 )
        return d ** 2

    def left_midpoint( self, n, positions ):
        x1, y1, x2, y2 = self.boundary_in( n, positions )
        return ( x1, (y1 + y2) / 2.0 )

    def right_midpoint( self, n, positions ):
        x1, y1, x2, y2 = self.boundary_in( n, positions )
        return ( x2, (y1 + y2) / 2.0 )
    
    def lower_midpoint( self, n, positions ):
        x1, y1, x2, y2 = self.boundary_in( n, positions )
        return ( (x1 + x2) / 2.0, y2 )

    def upper_midpoint( self, n, positions ):
        x1, y1, x2, y2 = self.boundary_in( n, positions )
        return ( (x1 + x2) / 2.0, y1 )
                  
    def penalty( self, positions ):
        total = 0.0

        for a, r, b in self.relations:
            overlap = self.overlap_in( a, b, positions )

            # TODO: maybe midpoint distance is the wrong thing,
            # we should weight gap between edges more heavily?
            if r == "adjacent-left":
                mb = self.left_midpoint( b, positions )
                ma = self.right_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.primary_scale + \
                    overlap * self.secondary_scale
            elif r == "adjacent-right":
                mb = self.right_midpoint( b, positions )
                ma = self.left_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.primary_scale + \
                    overlap * self.secondary_scale
            elif r == "adjacent-above":
                mb = self.upper_midpoint( b, positions )
                ma = self.lower_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.primary_scale + \
                    overlap * self.secondary_scale
            elif r == "adjacent-below":
                mb = self.lower_midpoint( b, positions )
                ma = self.upper_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.primary_scale + \
                    overlap * self.secondary_scale
            elif r == "disjoint":
                total += overlap * self.primary_scale
            elif r == "place-left":
                mb = self.left_midpoint( b, positions )
                ma = self.right_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.secondary_scale + \
                    overlap * self.primary_scale
            elif r == "place-right":
                mb = self.right_midpoint( b, positions )
                ma = self.left_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.secondary_scale + \
                    overlap * self.primary_scale
            elif r == "place-above":
                mb = self.upper_midpoint( b, positions )
                ma = self.lower_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.secondary_scale + \
                    overlap * self.primary_scale
            elif r == "place-below":
                mb = self.lower_midpoint( b, positions )
                ma = self.upper_midpoint( a, positions )
                total += distance_sq( ma, mb ) * self.secondary_scale + \
                    overlap * self.primary_scale
            else:
                print( "Unhandled relation", r )
                
        return total

    def random_change( self, positions ):
        # We want moves that produce somewhat similar penalties, rather
        # than big jumps.  But moving just one bounding box at a time
        # may easily get stuck in local minima.  So we'll move 1, 2 or 3
        # by an amount up to their width and height.

        # The size of the move should probably decrease with temperature.

        if len( self.movable ) > 1:
            a,b = random.sample( self.movable, 2 )
        else:
            a = random.sample( self.movable, 1 )[0]
            b = None
            
        np = positions.copy()

        scale = 1.0
        if self.temperature < 200:
            # 200 = 1.0
            #  50 = 0.5
            #  12.5 = 0.25
            scale = math.sqrt( self.temperature / 200.0 )

        bb_a = self.bounding_box( a )
        a_width = bb_a.x2 - bb_a.x1
        a_height = bb_a.y2 - bb_a.y1
        #print( "Range: ", a_width *scale, a_height *scale )
        
        np[a] = ( np[a][0] + random.uniform( -a_width * scale,
                                             a_width * scale ),
                  np[a][1] + random.uniform( -a_height * scale,
                                             a_height * scale ) )
        
        if b is not None and random.random() < 0.3:
            bb_b = self.bounding_box( b )
            b_width = bb_b.x2 - bb_b.x1
            b_height = bb_b.y2 - bb_b.y1
            np[b] = ( np[b][0] + random.uniform( -b_width * scale,
                                                 b_width * scale ),
                      np[b][1] + random.uniform( -b_height * scale,
                                                 b_height * scale ) )
        
        return np
        
    def initial_temperature( self ):
        num_samples = 100
        prob_accept = 0.8
        current = dict( self.current )
        val = self.penalty( current )
        total_increases = 0.0
        num_increases = 0
        
        for i in range( num_samples ):
            np = self.random_change( current )
            nv = self.penalty( np )
            if nv > val:
                total_increases += ( nv - val )
                num_increases += 1
            # Accept always
            current = np
            val = nv

        if self.verbose:
            print( "Num increases:", num_increases )
            print( "Total increases:", total_increases )
        if num_increases == 0:
            return 1000.0
        else:
            return - (total_increases / num_increases) / math.log( prob_accept )
        
    def decrease_temperature( self, temp ):
        return temp * 0.95

    def probability_accept( self, e1, e2, temp ):
        if e2 < e1:
            return 1.0
        else:
            return math.exp( (e1 - e2) / temp )
        
    def annealing_iter( self ):
        step = self.random_change( self.current )
        penalty = self.penalty( step )
        p = self.probability_accept( self.current_penalty, penalty, self.temperature )
        if self.verbose:
            print( "delta", self.current_penalty - penalty, "prob", p )
        if random.random() <= p:
            self.current = step
            self.current_penalty = penalty
            if self.current_penalty < self.best_penalty:
                self.best = self.current
                self.best_penalty = self.current_penalty
                self.best_temperature = self.temperature
            return True
        
        return False

    def annealing( self, num_iterations = None ):
        min_temperature = 0.1
        if num_iterations is None:
            num_iterations = len( self.relations ) * 20
        max_accepts = 100
        accept_num = 0.0
        accept_denom = 0.0
        
        while self.temperature > min_temperature:
            prev_best = self.best_penalty
            num_accepts = 0
            for i in range( num_iterations ):
                accept_denom += 1
                if self.annealing_iter():
                    #print( "Accept", self.current )
                    for m in self.movable:
                        self.paths[m].append( self.current[m] )
                    self.penalties.append( self.current_penalty )
                    self.temps.append( self.temperature )
                    num_accepts += 1
                    accept_num += 1
                    if num_accepts >= max_accepts:
                        break
            if self.best_penalty == prev_best:
                if self.verbose:
                    print( "No improvement at temperature", self.temperature )
                    ratio = accept_num / accept_denom
                    print( "Acceptance ratio:", ratio )
                
            self.temperature = self.decrease_temperature( self.temperature )
            if self.verbose:
                print( "*** Lowered temperature to", self.temperature )

        print( "Final penalty:", self.current_penalty )
        print( "Best penalty:", self.best_penalty, "at temperature", self.best_temperature )
    

def distance( a, b ):
    x1,y1 = a
    x2,y2 = b
    return math.sqrt( (x1-x2)**2 + (y1-y2)**2 )

def distance_sq( a, b ):
    x1,y1 = a
    x2,y2 = b
    return (x1-x2)**2 + (y1-y2)**2

class FakeElement(object):
    def __init__( self, x1, y1, x2, y2 ):
        self.bounding_box = self
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        
if __name__ == "__main__":
    g = nx.DiGraph()
    a = FakeElement( 10, 10, 20, 20 )
    b = FakeElement( 10, 10, 20, 20 )
    c = FakeElement( 10, 10, 20, 20 )
    d = FakeElement( 10, 10, 20, 20 )
    g.add_node( "a", drawn=a ) 
    g.add_node( "b", drawn=b ) 
    g.add_node( "c", drawn=c ) 
    g.add_node( "d", drawn=d ) 
    s = Solver( g )
    s.verbose = True
    s.add_edge( "a", "place-left", "b" )
    s.add_edge( "c", "place-left", "b" )
    s.add_edge( "a", "disjoint", "c" )
    s.add_edge( "d", "adjacent-left", "a" )

    s.start()
    s.annealing()
    print( "Best solution found:" )
    print( s.best_penalty )
    print( s.best )
    print( "at temperature", s.best_temperature )

    #plt.plot( [p[0] for p in s.paths["a"]],
    #          [p[1] for p in s.paths["a"]] )
    #plt.plot( [p[0] for p in s.paths["c"]],
    #          [p[1] for p in s.paths["c"]] )
    #plt.show()

    if False:
        recB = patches.Rectangle((10,10),10,10,linewidth=1,
                                 edgecolor='black',facecolor='none')
        recA = patches.Rectangle(s.boundary_in( 'a', s.best )[:2],10,10,linewidth=1,
                                 edgecolor='black',facecolor='none')
        recC = patches.Rectangle(s.boundary_in( 'c', s.best )[:2],10,10,linewidth=1,
                                 edgecolor='black',facecolor='none')
        ax = plt.gca()
        ax.add_patch( recA )
        ax.add_patch( recB )
        ax.add_patch( recC )


    plt.show()

    plt.plot( s.penalties )
    plt.plot( s.temps )

    plt.show()
    
