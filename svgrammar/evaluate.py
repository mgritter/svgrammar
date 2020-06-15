import networkx as nx

class Evaluation(object):
    def __init__( self, graph, in_list = False ):
        self.graph = graph
        self.in_list = in_list
        self.funcs = {
            "!" : self.bang_value,
            "+" : self.plus_value,
            "rgb" : self.rgb_value,
            "##" : self.concat_value,
            "translate" : self.translate_value,
            "scale" : self.translate_value,
            "skewX" : self.angle_value,
            "skewY" : self.angle_value,
            "rotate" : self.angle_value,            
            }
    

    def successors( self, n ):
        if self.in_list:
            return [ j for i,j,tag in self.graph.out_edges( n, data="tag" )
                     if tag != "next" ]
        else:
            return self.graph.successors( n )

    def list_successors( self, n ):
        assert self.in_list
        
        return [ j for i,j,tag in self.graph.out_edges( n, data="tag" )
                 if tag == "next" ]
        
    def children( self, n ):
        if self.in_list:
            return [ (tag,j) for i,j,tag in self.graph.out_edges( n, data="tag" )
                     if tag != "next" ]
        else:
            return [ (tag,j) for i,j,tag in self.graph.out_edges( n, data="tag" ) ]
                
        
    def sorted_successors( self, n ):
        return [ j for tag,j in sorted( self.children( n ) ) ]

    def successor_dictionary( self, n ):
        kv = {}
        for t, j in self.children( n ):
            if t is None:
                continue
            if t in kv:
                raise Exception( "Duplicate keyword {} in node {}".format( j, n ) )
            kv[t] = j
            
        return kv

    def successor_value_dictionary( self, n ):
        kv = {}
        for tag, j in self.children( n ):
            if tag is None:
                continue
            if tag in kv:
                raise Exception( "Duplicate keyword {} in node {}".format( tag, n ) )
            kv[tag] = self.node_value( j, [n] )
            
        return kv

    def successor_value_dictionary_with_lists( self, n, list_attrs ):
        # Interpret edges with tags in list_attrs as the start of a list
        # rather than a string value.
        kv = {}
        for tag, j in self.children( n ):
            if tag is None:
                continue
            if tag in kv:
                raise Exception( "Duplicate keyword {} in node {}".format( tag, n ) )
            if tag in list_attrs:
                e_list = Evaluation( self.graph, in_list = True )
                kv[tag] = e_list.list_value( j, [n] )
            else:
                kv[tag] = self.node_value( j, [n] )
                
            
        return kv

    def bang_value( self, n, visited ):
        successors = list( self.successors( n ) )
        if len( successors ) > 1:
            raise Exception( "Too many children in '!' node '" + str( n ) + "'" )
        return self.node_value( successors[0], visited )

    def plus_value( self, n, visited ):
        total = 0.0
        for nn in self.successors( n ):
            text = self.node_value( nn, visited )
            try:
                total += float( text )
            except ValueError:
                # Silently treat as zero
                continue
        return str( total )

    def concat_value( self, n, visited ):
        vals = [ self.node_value( j, visited )
                 for j in self.sorted_successors( n ) ]
        return " ".join( vals )

    def float_or_zero( self, children, key, visited ):
        if key not in children:
            return 0
        
        try:
            return float( self.node_value( children[key], visited ) )
        except ValueError:
            return 0
                
    def int_or_zero( self, children, key, visited ):
        if key not in children:
            return 0
        
        try:
            return int( self.node_value( children[key], visited ) )
        except ValueError:
            return 0
                
    def rgb_value( self, n, visited ):
        d = self.successor_dictionary( n )
        red = min( self.int_or_zero( d, "r", visited ), 255 )
        green = min( self.int_or_zero( d, "g", visited ), 255 )
        blue = min( self.int_or_zero( d, "b", visited ), 255 )
        return "rgb({},{},{})".format( red, green, blue )        

    def translate_value( self, n, visited ):
        d = self.successor_dictionary( n )
        x = self.float_or_zero( d, "x", visited )
        y = self.float_or_zero( d, "y", visited )
        return "{}({},{})".format( self.graph.nodes[n]["tag"], x,y )
    
    def angle_value( self, n, visited ):
        # FIXME: does SVG allow a non-numeric value here, like a
        # definition?
        children = self.successor_dictionary( n )
        if "d" in children:
            d = self.float_or_zero( children, "d", visited )
        elif len( children ) > 0:
            k = list( children.keys() )[0]
            d = self.float_or_zero( children, k, visited )
        else:
            d = 0
            
        return "{}({})".format( self.graph.nodes[n]["tag"], d )

    def node_value( self, n, visited ):
        # OK to visit the same node more than once, just not as a child
        # of itself.
        if n in visited:
            raise Exception( "Circular evaluation at node '" + str( n ) + "'" )

        if "tag" not in self.graph.nodes[n]:
            return ""

        # Cached value
        if "value" in self.graph.nodes[n]:
            return self.graph.nodes[n]["value"]

        tag = self.graph.nodes[n]["tag"]
        if tag in self.funcs:
                val = self.funcs[tag]( n, visited + [n] )
                self.graph.nodes[n]["value"] = val
                return val
        else:
                return tag
        
    def list_value( self, n, visited ):
        assert self.in_list
        
        v = self.node_value( n, visited )
        list_next = self.list_successors( n )
        ret = [v]
        for ln in list_next:
            ret += self.list_value( ln, visited + [n] )
        return ret
        
def extract_all_attributes( g, n, list_attrs = [] ):
    ev = Evaluation( g, in_list = False )
    return ev.successor_value_dictionary_with_lists( n, list_attrs )


