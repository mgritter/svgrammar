"""Bounding box data structure and calculations."""

class BoundingBox(object):
    def __init__( self ):
        self.x1 = None
        self.y1 = None
        self.x2 = None
        self.y2 = None

class RectangleBoundingBox(BoundingBox):
    def __init__( self, x, y, width, height )
        super.__init__( self )
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

class CircleBoundingBox(BoundingBox):
    def __init__( self, x, y, radius )
        super.__init__( self )
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
        super.__init__( self )
        
    def addElement( self, bb ):
        self.x1 = none_min( self.x1, bb.x1 )
        self.y1 = none_min( self.y1, bb.y1 )
        self.x2 = none_min( self.x2, bb.x2 )
        self.y2 = none_min( self.y2, bb.y2 )

    
        
                
