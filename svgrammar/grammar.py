import soffit.application as soffit
import soffit.display as display
import svgrammar.render as render
import sys
from pathlib import Path

def main():
    if len( sys.argv ) < 2 or len( sys.argv ) > 3:
        print( "Usage: python -m svgrammar <grammar file> [<output file>]" )
        sys.exit( 1 )

    grammarFile = Path( sys.argv[1] )
    if len( sys.argv ) > 2:
        outputFile = Path( sys.argv[2] )
    else:
        outputFile = grammarFile.with_suffix( ".svg" )
            
    grammar = soffit.loadGrammar( grammarFile )
    a = soffit.ApplicationState( grammar = grammar,
                                 initialGraph = grammar.start )
    a.run( 1000 )

    display.drawSvg( a.graph, "expanded-graph.svg" )
    d = render.graph_to_svg( a.graph )
    d.saveas( outputFile, pretty=True )
    
