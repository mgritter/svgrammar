"""Bounding box data structure and calculations."""
import re

translate_re = re.compile( "translate\(\s*(-?\d+(\.\d+)?)(\s+|\s*,\s*)(-?\d+(\.\d+)?)\s*\)" )
scale_re = re.compile( "scale\(\s*(-?\d+(\.\d+)?)(\s+|\s*,\s*)(-?\d+(\.\d+)?)\s*\)" )

def parse_transforms( s ):
    txs = []

    while len( s ) > 0:
        m = translate_re.match( s )
        if m is not None:
            txs.append( ( "translate", float( m.group(1) ), float( m.group(4) ) ) )
            s = s[len(m.group(0)):].lstrip()
            continue

        m = scale_re.match( s )
        if m is not None:
            txs.append( ( "scale", float( m.group(1) ), float( m.group(4) ) ) )
            s = s[len(m.group(0)):].lstrip()
            continue

        print( "Warning: unmatched transform '{}'".format( transform ) )
        break

    return txs
    
    
class BoundingBox(object):
    def __init__( self ):
        self.x1 = None
        self.y1 = None
        self.x2 = None
        self.y2 = None


    def applyTransform( self, transform ):
        # TODO: handle rotate

        # Apply in reverse order
        for t in reversed( parse_transforms( transform ) ):
            if t[0] == "translate":
                _, dx, dy = t
                #print( "Translating by", dx, dy )
                self.x1 += dx
                self.x2 += dx
                self.y1 += dy
                self.y2 += dy
            elif t[0] == "scale":
                _, sx, sy = t
                self.x1 *= sx
                self.x2 *= sx
                if self.x2 < self.x1:
                    self.x1, self.x2 = self.x2, self.x1
                self.y1 *= sy
                self.y2 *= sy
                if self.y2 < self.y1:
                    self.y1, self.y2 = self.y2, self.y1
            else:
                print( "Warning: unhandled transform '{}'".format( t ) )

    def translate( self, dx, dy ):
        self.x1 += dx
        self.x2 += dx
        self.y1 += dy
        self.y2 += dy
        
    def __str__( self ):
        return "({},{})--({},{})".format( self.x1, self.y1, self.x2, self.y2 )

class RectangleBoundingBox(BoundingBox):
    def __init__( self, x, y, width, height ):
        super().__init__()
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

class CircleBoundingBox(BoundingBox):
    def __init__( self, x, y, radius ):
        super().__init__()
        self.x1 = x - radius
        self.y1 = y - radius
        self.x2 = x + radius
        self.y2 = y + radius

def none_min( a, b ):
    if a is None:
        return b
    if b is None:
        return a
    if a < b:
        return a
    else:
        return b

def none_max( a, b ):
    if a is None:
        return b
    if b is None:
        return a
    if a > b:
        return a
    else:
        return b

class GroupBoundingBox(BoundingBox):
    def __init__( self ):
        super().__init__()
        
    def addElement( self, bb ):
        self.x1 = none_min( self.x1, bb.x1 )
        self.y1 = none_min( self.y1, bb.y1 )
        self.x2 = none_max( self.x2, bb.x2 )
        self.y2 = none_max( self.y2, bb.y2 )

# TODO: use a real parser and handle junk like M100-100 which is technically
# legal.
# TODO: also handle commas
# TODO: and implicit lines/curves
# TODO: and actually calculate bezier extrema?
# TODO: "S" and "T"
def simulate_path( d ):
    path = iter( d.split() )
    x = None
    y = None
    firstPoint = None
    
    while True:
        try:
            kw = next( path )
        except StopIteration:
            return
        
        if kw == "M" or kw == "L":
            x = float( next( path ) )
            y = float( next( path ) )
            if firstPoint is None:
                firstPoint = (x,y)
            yield (x,y)
        elif kw == "m" or kw == "l":
            x += float( next( path ) )
            y += float( next( path ) )
            yield (x,y)
        elif kw == "H":
            x = float( next( path ) )
            yield (x,y)
        elif kw == "V":
            y = float( next( path ) )
            yield (x,y)
        elif kw == "h":
            x += float( next( path ) )
            yield (x,y)
        elif kw == "v":
            y += float( next( path ) )
            yield (x,y)
        elif kw == "Z" or kw == "z":
            x,y = firstPoint
        elif kw == "C":
            cx1, cy1 = float( next(path) ), float( next(path) )
            cx2, cy2 = float( next(path) ), float( next(path) )
            x = float( next(path) )
            y = float( next(path) )
            yield (x,y)
        elif kw == "c":
            cx1, cy1 = x + float( next(path) ), y + float( next(path) )
            cx2, cy2 = x + float( next(path) ), y + float( next(path) )
            x += float( next(path) )
            y += float( next(path) )
            yield (x,y)
        elif kw == "Q":
            cx1, cy1 = float( next(path) ), float( next(path) )
            x = float( next(path) )
            y = float( next(path) )
            yield (x,y)
        elif kw == "q":
            cx1, cy1 = x + float( next(path) ), y + float( next(path) )
            x += float( next(path) )
            y += float( next(path) )
            yield (x,y)
        elif kw == "A":
            # A rx ry x-axis-rotation large-arc-flag sweep-flag x y
            # a rx ry x-axis-rotation large-arc-flag sweep-flag dx dy
            rx, ry = float( next(path) ), float( next(path) )
            rot = float( next(path) )
            laf, sw = float( next(path) ), float( next(path) )
            x = float( next(path) )
            y = float( next(path) )
            yield (x,y)
        elif kw == "a":
            rx, ry = float( next(path) ), float( next(path) )
            rot = float( next(path) )
            laf, sw = float( next(path) ), float( next(path) )
            x += float( next(path) )
            y += float( next(path) )
            yield (x,y)
        else:
            raise Exception( "Unhandled SVG path command '{}'".format( kw ) )
    
class PathBoundingBox(BoundingBox):
    def __init__( self, d ):
        super().__init__()
        for x,y in simulate_path( d ):
            #print( "Path visited", (x,y) )
            self.x1 = none_min( self.x1, x )
            self.y1 = none_min( self.y1, y )
            self.x2 = none_max( self.x2, x )
            self.y2 = none_max( self.y2, y )
            

            
    
        
                
