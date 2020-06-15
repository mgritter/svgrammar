import networkx as nx
import svgwrite
from .evaluate import extract_all_attributes
import svgrammar.bounding as bounding
from .placement import Solver

class Element(object):
    def __init__( self, n, svg, bb ):
        self.svg_element = svg
        self.bounding_box = bb
        self.node = n
        
    def addElement( self, other ):
        self.bounding_box.addElement( other.bounding_box )
        self.svg_element.add( other.svg_element )

    def doTransform( self ):
        if "transform" in self.svg_element.attribs:
            self.bounding_box.applyTransform( self.svg_element.attribs["transform"] )

    def translate( self, dx, dy ):
        self.svg_element.translate( dx, dy )
        self.bounding_box.translate( dx, dy )
        
svgElements = [ 'g', 'svg', 'rect', 'circle', 'path' ]

def consume_float( attr, key, default ):
    if key in attr:
        try:
            val = float( attr[key] )
            del attr[key]
            return val
        except ValueError:
            pass
        
    return default

# Filter out any unexpected attributes, or svgwrite will throw an exception.
validator = svgwrite.validator2.get_validator( "full" )

placement_relations = set( ["adjacent-left", "adjacent-right",
                            "adjacent-above", "adjacent-below",
                            "place-left", "place-right",
                            "place-above", "place-below",
                            "disjoint" ])
expected_invalid = placement_relations.union( set( ["below"] ) )

def strip_invalid_attributes( elementname, attr ):
    for k in list( attr.keys() ):
        try:
            validator.check_svg_attribute_value( elementname, k, attr[k] )
        except ValueError:
            if k not in expected_invalid:
                print( 'Removed attribute {}="{}"'.format( k, attr[k] ) )
            del attr[k]
            
    return attr
    
def draw_circle( drawing, g, n ):
    attr = extract_all_attributes( g, n )
    x = consume_float( attr, "cx", 0 )
    y = consume_float( attr, "cy", 0 )
    radius = consume_float( attr, "r", 0 )
    strip_invalid_attributes( "circle", attr )

    return Element( n,
                    drawing.circle( (x, y), radius, **attr),
                    bounding.CircleBoundingBox( x, y, radius ) )
        
def draw_rect( drawing, g, n ):
    attr = extract_all_attributes( g, n )
    x = consume_float( attr, "x", 0 )
    y = consume_float( attr, "y", 0 )
    width = consume_float( attr, "width", 0 )
    height = consume_float( attr, "height", 0 )
    strip_invalid_attributes( "rect", attr )

    return Element( n,
                    drawing.rect( (x, y), (width, height), **attr ),
                    bounding.RectangleBoundingBox( x, y, width, height ) )

def draw_path( drawing, g, n ):
    attr = extract_all_attributes( g, n, ["d_list"] )
    if "d_list" in attr:
        d = " ".join( attr.pop( "d_list" ) )
        if "d" in attr:
            print( "Both d_list and d found at node {}", n )
            del attr["d"]
    elif "d" in attr:
        d = attr.pop( "d" )
    else:
        d = ""
        
    strip_invalid_attributes( "path", attr )
    return Element( n,
                    drawing.path( d, **attr ),
                    bounding.PathBoundingBox( d ) )

def create_group( drawing, g, n ):
    attr = extract_all_attributes( g, n )
    children = []
    for i, j, t in g.out_edges( n, data="tag" ):
        if t is None:
            children.append( j )
            
    strip_invalid_attributes( "g", attr )
    element = Element( n,
                       drawing.g( **attr ),
                       bounding.GroupBoundingBox() )
    return element, find_order( g, children )

    
def render_to_drawing( drawing, in_group, g, elems, parents = [] ):
    elems = list( elems )
    
    # Assemble drawing first
    for e in elems:
        if e in parents:
            raise Exception( "Circular rendering at node '" + str( e ) + "'" )
            
        tag = g.nodes[e]["tag"]
        drawn = None
        
        if tag == "rect":
            drawn = draw_rect( drawing, g, e )
        elif tag == "circle":
            drawn = draw_circle( drawing, g, e )
        elif tag == "path":
            drawn = draw_path( drawing, g, e )
        elif tag == "g":
            drawn, children = create_group( drawing, g, e )
            render_to_drawing( drawing, drawn, g, children, parents + [e] )

        if drawn is not None:
            g.nodes[e]["drawn"] = drawn
            drawn.doTransform()
            #print( "element", tag, "bounding box:", drawn.bounding_box )

    # Look for any placement attributes
    s = Solver( g )
    for e in elems:
        if "drawn" in g.nodes[e]:
            for i,j,t in g.out_edges( e, data="tag" ):
                if t in placement_relations:
                    if j not in elems:
                        print( "WARNING: ignoring cross-group placement {} -> {}".format( i, j ) )
                        continue
                    s.add_edge( i, t, j )

    
    if len( s.relations ) != 0:
        s.start()
        s.annealing()
        print( "Placements:", s.best )
        for n, (x,y) in s.best.items():
            (x,y) = round_translation(x,y)
            g.nodes[n]["drawn"].translate( x, y )
            
    # Add final locations to element
    for e in elems:
        if "drawn" in g.nodes[e]:
            in_group.addElement( g.nodes[e]["drawn"] )

def round_translation(x,y):
    # FIXME: scale based on size of image?
    return ( round( x, 6 ),
             round( y, 6 ) )
        
def graph_to_svg( g ):
    svg, elems = top_level_elements( g )
    
    d = svgwrite.Drawing( size=("8in","8in") )
    if svg is not None:
        attr = extract_all_attributes( g, svg )
        width = consume_int( attr, "width", 200 )
        height = consume_int( attr, "height", 200 )
        x = consume_int( attr, "x", 0 )
        y = consume_int( attr, "y", 0 )
        d.viewbox( x, y, width, height )
        # TODO: remaining attributes?
    else:
        d.viewbox( 0, 0, 200, 200 )

    container = Element( svg, d, bounding.GroupBoundingBox() )
    render_to_drawing( d, container, g, elems )
    
    return d

def find_order( graph, nodes ):
    orderGraph = nx.DiGraph()
    nodes = set( nodes )
    
    for n in nodes:
        orderGraph.add_node( n )
        for i, j, t in graph.out_edges( n, data="tag" ):
            if t == "below":
                # FIXME: cross-level constraints?
                if j in nodes:
                    orderGraph.add_edge( i, j )

    return nx.algorithms.dag.topological_sort( orderGraph )
    
# How do we tell whether an element is "top-level"?
# This is the case whenever there is no inclusion path to it from
# a group.
#
# [g] --> [elem] <-- [g] is possible.
# [g] --> [!] --> [elem]  is also allowed.
# In these case a copy of the element is included in *every* group.
#
# TODO: propogate order constraints from sub-elements up to the
# top layer, somehow?
def top_level_elements( g ):
    """Find all recognized top-level tags within the graph, and sort them by
    z-order."""
    untaggedEdges = [ (i,j) for i,j,t in g.edges( data="tag" ) if t is None ]
    inclusionGraph = g.edge_subgraph( untaggedEdges ) 
    
    topTag = None
    topLevel = set()
    
    for n, t in g.nodes( data="tag" ):
        if t == "svg":
            topTag = n
            # All the elements included are top-level by definition
            # though this is not required
            if n in inclusionGraph.nodes:
                for i, j in inclusionGraph.out_edges( n ):
                    topLevel.add( j )
        elif t in svgElements:
            if n in topLevel:
                continue
            if not has_group_parent( inclusionGraph, n ):
                topLevel.add( n )

    #print( "Top level: ", topLevel )
    
    return topTag, find_order( g, topLevel )


def has_group_parent( g, n ):
    if n not in g.nodes:
        return False
    
    ancestors = nx.algorithms.traversal.depth_first_search.dfs_preorder_nodes( g.reverse(), n )
    for a in ancestors:
        if a == n:
            continue
        if g.nodes[a].get( 'tag', None ) == 'g':
            # print( "Node", n, "has ancestor", a )
            return True
    return False

                    
                        
        
