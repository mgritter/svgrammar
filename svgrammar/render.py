import networkx as nx
import svgwrite
from .evaluate import extract_all_attributes

svgElements = [ 'g', 'svg', 'rect', 'circle' ]

def consume_float( attr, key, default ):
    if key in attr:
        try:
            val = float( attr[key] )
            del attr[key]
            return val
        except ValueError:
            pass
        
    return default

# FIXME: need to filter any disallowed attributes or
# svgwrite will error out.

validator = svgwrite.validator2.get_validator( "full" )

expected_invalid = set( ["below", "adjacent-left", "adjacent-right",
                         "adjacent-above", "adjacent-below", "place-left",
                         "place-right", "place-above", "place-below" ])

def strip_invalid_attributes( elementname, attr ):
    for k in list( attr.keys() ):
        try:
            validator.check_svg_attribute_value( elementname, k, attr[k] )
        except ValueError:
            if k not in expected_invalid:
                print( 'Removed attribute {}="{}"'.format( k, attr[k] ) )
            del attr[k]
            
    return attr
    
def draw_circle( drawing, in_group, g, n ):
    attr = extract_all_attributes( g, n )
    x = consume_float( attr, "cx", 0 )
    y = consume_float( attr, "cy", 0 )
    radius = consume_float( attr, "r", 0 )
    strip_invalid_attributes( "circle", attr )
    in_group.add( drawing.circle( (x, y), radius, **attr) )
        
def draw_rect( drawing, in_group, g, n ):
    attr = extract_all_attributes( g, n )
    x = consume_float( attr, "x", 0 )
    y = consume_float( attr, "y", 0 )
    width = consume_float( attr, "width", 0 )
    height = consume_float( attr, "height", 0 )
    strip_invalid_attributes( "rect", attr )

    in_group.add( drawing.rect( (x, y), (width, height), **attr ) )

def create_group( drawing, in_group, g, n ):
    attr = extract_all_attributes( g, n )
    children = []
    for i, j, t in g.out_edges( n, data="tag" ):
        if t is None:
            children.append( j )
            
    strip_invalid_attributes( "g", attr )
    group = drawing.g( **attr )    
    in_group.add( group )

    return group, find_order( g, children )
    
def render_to_drawing( drawing, in_group, g, elems, parents = [] ):
    for e in elems:
        if e in parents:
            raise Exception( "Circular rendering at node '" + str( e ) + "'" )
            
        tag = g.nodes[e]["tag"]
        if tag == "rect":
            draw_rect( drawing, in_group, g, e )
        elif tag == "circle":
            draw_circle( drawing, in_group, g, e )
        elif tag == "g":
            group, children = create_group( drawing, in_group, g, e )
            render_to_drawing( drawing, group, g, children, parents + [e] )
    
def graph_to_svg( g ):
    # TODO: placement
    # TODO: z-ordering within each group
    svg, elems = top_level_elements( g )
    
    d = svgwrite.Drawing( size=("8in","8in") )
    if svg is not None:
        attr = extract_all_attributes( g, svg )
        width = consume_int( attr, "width", 200 )
        height = consume_int( attr, "height", 200 )
        x = consume_int( attr, "x", 0 )
        y = consume_int( attr, "y", 0 )
        d.viewbox( x, y, width, height )
        # TODO: remaining elements?
    else:
        d.viewbox( 0, 0, 200, 200 )

    render_to_drawing( d, d, g, elems )

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

                    
                        
        
