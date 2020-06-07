# svgrammar

This project augments Soffit with the ability to output SVG shapes.

A graph node tagged with a SVG label will be added to the output. Attributes
should be connected with labelled edges; for example

```
A [rect];
A->B [x]; B[10];
A->C [y]; C[10];
A->D [stroke]; D[red];
A->E [width]; E[20];
A->F [height]; F[20];
```

To permit re-use, any tag name starting with ! will be ignored, and
the attribute value will be retrieved from a child of that node.
(Soffit does not permit multigraphs.)  So the example above can be
rendered as:

```
A [rect];
A->B [x]; B[10];
A->C [y]; C[!]; C->B;
A->D [stroke]; D[red];
A->E [width]; E[!]; E->F;
A->F [height]; F[20];
```

An SVG group ("g" tag) has unlabelled edges to all of its components.

Supported elements:
 * svg
 * g
 * circ
 * rect
 * path

## paths

A path can be given a simple string as a "d" child, as usual; this string
can be constructed with concatenation with ##.

However, we also permit a linked list of path elements. Use the edge tag
d_head to mark the head of such a list, and the edge tag "next" to mark
the next element of the list.  If any elements have multiple next edges
then we visit them in random order.

```
A [path];
A->HEAD [d_list]; HEAD [M]
HEAD->X [next]; X[20]
X->Y [next]; Y[20]
Y->Z [next]; ...
```

The individual nodes in the list may be expressions, as described below.

## relative placements

An SVG group can be placed relative to other groups by adding edges tagged with the relative
placements.

G1 -> G2 [adjacent-left]    ;; minimize edge-to-edge distance, then overlap
G1 -> G2 [adjacent-right]
G1 -> G2 [adjacent-above]
G1 -> G2 [adjacent-below]

G1 -> G2 [place-left]       ;; minimize overlap, then edge-to-edge distaince
G1 -> G2 [place-right]
G1 -> G2 [place-above]
G1 -> G2 [place-below]

A bounding box will be used to try to satisfy these constraints.  Gradient descent will be used
to find a placement that minimizes the  when the requests are inconsistent.  A weighting of
100:1 will be used between the primary and secondary goals.

Unrelated elements can also be ordered on the Z axis with

G1 -> G2 [below]

## Math assistance

A node labelled "+" will evaluate to the sum of any child nodes.

## Color

A node tagged "rgb" will evaluate to an RGBA color value, e.g.

X[rgb]; X->R[r]; X->B[b]; X->G[g];

where R, G, B are numeric expressions. Any missing ones will be filled in with zero.

## Transformations

A node tagged '##' will concatenate its elements in alphanumeric order of their tags, with spaces in between.  This can be used to combine multiple transformations.

A node tagged 'translate' or 'scale' combines the values of its 'x' and 'y' children, zero if absent.

A node tagged 'rotate', 'skewX', or 'skewY' takes any child as its angle value (in degrees.)

(TODO: we could replace all of these with a "function application" operator?)

## Gradient

TODO

## Top level attributes

A svg tag may be used to contain  attributes such as viewBox.  Multiple SVG tags result in
undefined behavior.
