import networkx as nx
import svgwrite

svgElements = [ 'g', 'svg', 'rect', 'circle' ]

def eval_expression( g, n, visited = [] ):
    # OK to visit the same node more than once, just not as a child
    # of itself.
    if n in visited:
        raise Exception( "Circular evaluation at node '" + str( n ) + "'" )
    
    if "tag" not in g.nodes[n]:
        return ""
    tag = g.nodes[n]["tag"]
    if tag == "!":
        successors = list( g.successors( n ) )
        if len( successors ) > 1:
            raise Exception( "Too many children in '!' node '" + str( n ) + "'" )
        return eval_expression( g, successors[0], visited + [n] )

    if tag == "+":
        if "value" in g.nodes[n]:
            return g.nodes[n]["value"]
        
        total = 0
        for nn in g.successors( n ):
            text = eval_expression( g, nn, visited + [n] )
            try:
                total += int( text )
            except ValueError:
                # Silently treat as zero
                continue
        g.nodes[n]["value"] = str( total )
        return str( total )

    if tag == "rgb":
        d = extract_attributes( g, n, visited + [n] )
        red = min( int_or_zero( d, "r" ), 255 )
        green = min( int_or_zero( d, "g" ), 255 )
        blue = min( int_or_zero( d, "b" ), 255 )
        return "rgb({},{},{})".format( red, green, blue )

    if tag == "##":
        d = extract_attributes( g, n, visited + [n] )
        return " ".join( d[k] for k in sorted( d.keys() ) )

    if tag == "translate" or tag == "scale":
        d = extract_attributes( g, n, visited + [n] )
        x = int_or_zero( d, "x" )
        y = int_or_zero( d, "y" )
        return "{}({},{})".format( tag, x,y )

    if tag == "skewX" or tag == "skewY" or tag == "rotate":
        # FIXME: allow unlabeled?
        d = extract_attributes( g, n, visited + [n] )
        if "d" in d:
            deg = int_or_zero( d, "d" )
        else:
            deg = int_or_zero( d, list( d.keys() )[0] )
        return "{}({})".format( tag, deg )

    return tag

def int_or_zero( d, key ):
    try:
        return int( d.get( key, 0 ) )
    except ValueError:
        return 0
    
def extract_attributes( g, n, visited = [] ):
    kv = {}
    for i, j, t in g.out_edges( n, data="tag" ):
        if t is not None:
            kv[t] = eval_expression( g, j, visited )
    return kv

def consume_int( attr, key, default ):
    if key in attr:
        try:
            val = int( attr[key] )
            del attr[key]
            return val
        except ValueError:
            pass
        
    return default

def draw_circle( drawing, in_group, g, n ):
    attr = extract_attributes( g, n )
    x = consume_int( attr, "cx", 0 )
    y = consume_int( attr, "cy", 0 )
    radius = consume_int( attr, "r", 0 )
    in_group.add( drawing.circle( (x, y), radius, **attr) )
        
def draw_rect( drawing, in_group, g, n ):
    attr = extract_attributes( g, n )
    x = consume_int( attr, "x", 0 )
    y = consume_int( attr, "y", 0 )
    width = consume_int( attr, "width", 0 )
    height = consume_int( attr, "height", 0 )
    in_group.add( drawing.rect( (x, y), (width, height), **attr ) )

def create_group( drawing, in_group, g, n ):
    print( "Creating group for", n )
    attr = extract_attributes( g, n )
    children = []
    for i, j, t in g.out_edges( n, data="tag" ):
        print( "Out edge:", i, j, t )
        if t is None:
            children.append( j )
    group = drawing.g( **attr )    
    in_group.add( group )
    return group, children
    
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
        attr = extract_attributes( g, svg )
        width = consume_int( attr, "width", 200 )
        height = consume_int( attr, "height", 200 )
        x = consume_int( attr, "x", 0 )
        y = consume_int( attr, "y", 0 )
        d.viewbox( x, y, width, height )
    else:
        d.viewbox( 0, 0, 200, 200 )

    render_to_drawing( d, d, g, elems )

    return d
    
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
    orderGraph = nx.DiGraph()

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

    print( "Top level: ", topLevel )
    
    for n in topLevel:
        orderGraph.add_node( n )
        for i, j, t in g.out_edges( n, data="tag" ):
            if t == "below":
                # FIXME: cross-level constraints?
                if j not in topLevel:
                    orderGraph.add_edge( i, j )

    return topTag, nx.algorithms.dag.topological_sort( orderGraph )

def has_group_parent( g, n ):
    if n not in g.nodes:
        return False
    
    ancestors = nx.algorithms.traversal.depth_first_search.dfs_preorder_nodes( g.reverse(), n )
    for a in ancestors:
        if a == n:
            continue
        if g.nodes[a].get( 'tag', None ) == 'g':
            print( "Node", n, "has ancestor", a )
            return True
    return False

                    
                        
        
