#!/usr/bin/env python
# coding: utf-8

import itertools
import base64

import numpy as np
import pandas as pd
import plotly
import scipy.spatial
from plotly import express as px
from plotly import graph_objs as go
from umap import UMAP
from tqdm.notebook import tqdm
import wx

import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout, to_agraph
from IPython.display import Image

from pyphi import relations as rel


def get_screen_size():
    app = wx.App(False)
    width, height = wx.GetDisplaySize()
    return width, height


def flatten(iterable):
    return itertools.chain.from_iterable(iterable)


def feature_matrix(ces, relations):
    """Return a matrix representing each cause and effect in the CES.

    .. note::
        Assumes that causes and effects have been separated.
    """
    N = len(ces)
    M = len(relations)
    # Create a mapping from causes and effects to indices in the feature matrix
    index_map = {purview: i for i, purview in enumerate(ces)}
    # Initialize the feature vector
    features = np.zeros([N, M])
    # Assign features
    for j, relation in enumerate(relations):
        indices = [index_map[relatum] for relatum in relation.relata]
        # Create the column corresponding to the relation
        relation_features = np.zeros(N)
        # Assign 1s where the cause/effect purview is involved in the relation
        relation_features[indices] = 1
        # Assign the feature column to the feature matrix
        features[:, j] = relation_features
    return features


def get_coords(data, y=None, n_components=3, **params):

    """ if n_components <= 2:
        coords = np.zeros((len(data),2))
        for i in range(len(data)):
           coords[i][0] = i* 0.5
           coords[i][1] = i*0.5

    else:  """

    if n_components >= data.shape[0]:
        params["init"] = "random"

    umap = UMAP(
        n_components=n_components,
        metric="euclidean",
        n_neighbors=30,
        min_dist=0.5,
        **params,
    )
    coords = umap.fit_transform(data, y=y)

    return coords


def relation_vertex_indices(features, j):
    """Return the indices of the vertices for relation ``j``."""
    return features[:, j].nonzero()[0]


def all_triangles(vertices):
    """Return all triangles within a set of vertices."""
    return itertools.combinations(vertices, 3)


def all_edges(vertices):
    """Return all edges within a set of vertices."""
    return itertools.combinations(vertices, 2)


def make_label(nodes, node_labels=None):
    if node_labels is not None:
        nodes = node_labels.indices2labels(nodes)
    return "".join(nodes)


def label_mechanism(mice):
    return make_label(mice.mechanism, node_labels=mice.node_labels)


def label_mechanism_state(subsystem, distinction):
    mechanism_state = [subsystem.state[node] for node in distinction.mechanism]
    return "".join(str(node) for node in mechanism_state)


def label_purview(mice):
    return make_label(mice.purview, node_labels=mice.node_labels)


def label_state(mice):
    return [rel.maximal_state(mice)[0][node] for node in mice.purview]


def label_purview_state(mice):
    return "".join(str(x) for x in label_state(mice))


def label_relation(relation):
    relata = relation.relata

    relata_info = "<br>".join(
        [
            f"{label_mechanism(mice)} / {label_purview(mice)} [{mice.direction.name}]"
            for n, mice in enumerate(relata)
        ]
    )

    relation_info = f"<br>Relation purview: {make_label(relation.purview, relation.subsystem.node_labels)}<br>Relation φ = {phi_round(relation.phi)}<br>"

    return relata_info + relation_info


def hovertext_mechanism(distinction):
    return f"Distinction: {label_mechanism(distinction.cause)}<br>Cause: {label_purview(distinction.cause)}<br>Cause φ = {phi_round(distinction.cause.phi)}<br>Cause state: {[rel.maximal_state(distinction.cause)[0][i] for i in distinction.cause.purview]}<br>Effect: {label_purview(distinction.effect)}<br>Effect φ = {phi_round(distinction.effect.phi)}<br>Effect state: {[rel.maximal_state(distinction.effect)[0][i] for i in distinction.effect.purview]}"


def hovertext_purview(mice):
    return f"Distinction: {label_mechanism(mice)}<br>Direction: {mice.direction.name}<br>Purview: {label_purview(mice)}<br>φ = {phi_round(mice.phi)}<br>State: {[rel.maximal_state(mice)[0][i] for i in mice.purview]}"


def hovertext_relation(relation):
    relata = relation.relata

    relata_info = "".join(
        [
            f"<br>Distinction {n+1}: {label_mechanism(mice)}<br>Direction: {mice.direction.name}<br>Purview: {label_purview(mice)}<br>φ = {phi_round(mice.phi)}<br>State: {[rel.maximal_state(mice)[0][i] for i in mice.purview]}<br>"
            for n, mice in enumerate(relata)
        ]
    )

    relation_info = f"<br>Relation purview: {make_label(relation.purview, relation.subsystem.node_labels)}<br>Relation φ = {phi_round(relation.phi)}<br>"

    return f"<br>={len(relata)}-Relation=<br>" + relata_info + relation_info


def normalize_sizes(min_size, max_size, elements):
    phis = np.array([element.phi for element in elements])
    min_phi = phis.min()
    max_phi = phis.max()
    # Add exception in case all purviews have the same phi (e.g. monad case)
    if max_phi == min_phi:
        return [(min_size + max_size) / 2 for x in phis]
    else:
        return min_size + (
            ((phis - min_phi) * (max_size - min_size)) / (max_phi - min_phi)
        )


def phi_round(phi):
    return np.round(phi, 4)


def chunk_list(my_list, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(my_list), n):
        yield my_list[i : i + n]


def format_node(n, subsystem):
    node_format = {
        "label": subsystem.node_labels[n],
        "style": "filled" if subsystem.state[n] == 1 else "",
        "fillcolor": "black" if subsystem.state[n] == 1 else "",
        "fontcolor": "white" if subsystem.state[n] == 1 else "black",
    }
    return node_format


def save_digraph(
    subsystem, digraph_filename="digraph.png", plot_digraph=False, layout="dot"
):
    network = subsystem.network
    G = nx.DiGraph()

    for n in range(network.size):
        node_info = format_node(n, subsystem)
        G.add_node(
            node_info["label"],
            style=node_info["style"],
            fillcolor=node_info["fillcolor"],
            fontcolor=node_info["fontcolor"],
        )

    edges = [
        [format_node(i, subsystem)["label"] for i in n]
        for n in np.argwhere(subsystem.cm)
    ]

    G.add_edges_from(edges)
    G.graph["node"] = {"shape": "circle"}

    A = to_agraph(G)
    A.layout(layout)
    A.draw(digraph_filename)
    if plot_digraph:
        return Image(digraph_filename)


def get_edge_color(relation, colorcode_2_relations):
    if colorcode_2_relations:
        purview0 = list(relation.relata.purviews)[0]
        purview1 = list(relation.relata.purviews)[1]
        relation_purview = relation.purview
        # Isotext (mutual full-overlap)
        if purview0 == purview1 == relation_purview:
            return "fuchsia"
        # Sub/Supertext (inclusion / full-overlap)
        elif purview0 != purview1 and (
            all(n in purview1 for n in purview0) or all(n in purview0 for n in purview1)
        ):
            return "indigo"
        # Paratext (connection / partial-overlap)
        elif (purview0 == purview1 != relation_purview) or (
            any(n in purview1 for n in purview0)
            and not all(n in purview1 for n in purview0)
        ):
            return "cyan"
        else:
            raise ValueError(
                "Unexpected relation type, check function to cover all cases"
            )
    else:
        return "teal"


# This seperates cause and effect parts of features of purviews. For example, it separates labels, states, z-coordinates in the
# original combined list. Normally purview lists are in the shape of [featureOfCause1,featureOfEffect1,featureOfCause2...]
# by using this we can separate all those features into two lists, so that we can use them to show cause and effect purviews
# separately in the CES plot.

# WARNING: This doesn't work for coordinates.


def separate_cause_and_effect_purviews_for(given_list):
    causes_in_given_list = []
    effects_in_given_list = []

    for i in range(len(given_list)):
        if i % 2 == 0:
            causes_in_given_list.append(given_list[i])
        else:
            effects_in_given_list.append(given_list[i])

    return causes_in_given_list, effects_in_given_list


# This separates the xy coordinates of purviews.Similar to above the features treated in the above function,
# the coordinates are given in a "[x of c1, y of c1],
# [x of e1,y of e1],..." fashion and  with this function we can separate them to x and y of cause and effect purviews.


def separate_cause_and_effect_for(coords):

    causes_x = []
    effects_x = []
    causes_y = []
    effects_y = []

    for i in range(len(coords)):
        if i % 2 == 0:
            causes_x.append(coords[i][0])
            causes_y.append(coords[i][1])
        else:
            effects_x.append(coords[i][0])
            effects_y.append(coords[i][1])

    return causes_x, causes_y, effects_x, effects_y


# This is an experiment for separating relations on purviews so that we can have purview q-folds.
def purview_chunker(relations_list):
    purview_chunked_list = []
    purview_chunk = []
    index_chunk_list = []
    index_chunk = []
    index_chunk.append(0)
    previous_relation = relations_list[0]
    purview_chunk.append(previous_relation)
    for relation in relations_list:
        if (
            relation.mechanisms[0] == previous_relation.mechanisms[0]
            and relation.purview == previous_relation.purview
            and relation != previous_relation
        ):
            purview_chunk.append(relation)
            index_chunk.append(relations_list.index(relation))
        else:
            purview_chunked_list.append(purview_chunk)
            purview_chunk = []
            purview_chunk.append(relation)

            index_chunk_list.append(index_chunk)
            index_chunk = []
            index_chunk.append(relations_list.index(relation))

        previous_relation = relation

    return purview_chunked_list, index_chunk_list


def plot_ces(
    subsystem,
    ces,
    relations,
    network=None,
    max_order=3,
    cause_effect_offset=(0.3, 0, 0),
    mechanism_z_offset=(0.1),
    vertex_size_range=(10, 40),
    edge_size_range=(0.5, 4),
    surface_size_range=(0.005, 0.1),
    plot_dimentions=(768, 1366),
    mechanism_labels_size=15,
    state_labels_size=10,
    purview_labels_size=12,
    show_mechanism_labels=True,
    show_purview_labels="legendonly",
    show_vertices_mechanisms=True,
    show_vertices_purviews=True,
    show_edges="legendonly",
    show_mesh="legendonly",
    show_node_qfolds=False,
    show_mechanism_qfolds="legendonly",
    show_compound_purview_qfolds=True,
    show_relation_purview_qfolds=True,
    show_cause_per_mechanism_purview_qfolds=True,
    show_grid=False,
    network_name="",
    plot_title_size=20,
    eye_coordinates=(0.5, 0.5, 0.5),
    hovermode="x",
    digraph_filename="digraph.png",
    digraph_layout="dot",
    digraph_coords=(0, 1),
    digraph_size=(0.2, 0.3),
    save_plot_to_html=True,
    show_causal_model=True,
    order_on_z_axis=True,
    colorcode_2_relations=True,
    state_label_z_offset=0.1,
    left_margin=100,
    legend_title_size=12,
    legend_font_size=10,
    autosize=False,
):
    # Select only relations <= max_order
    relations = list(filter(lambda r: len(r.relata) <= max_order, relations))
    # Separate CES into causes and effects
    separated_ces = rel.separate_ces(ces)

    # Initialize figure
    fig = go.Figure()

    # Dimensionality reduction
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Create the features for each cause/effect based on their relations
    features = feature_matrix(separated_ces, relations)

    # Now we get one set of coordinates for the CES; these will then be offset to
    # get coordinates for causes and effects separately, so that causes/effects
    # are always near each other in the embedding.

    # Collapse rows of cause/effect belonging to the same distinction
    # NOTE: This depends on the implementation of `separate_ces`; causes and
    #       effects are assumed to be adjacent in the returned list
    umap_features = features[0::2] + features[1::2]
    if order_on_z_axis:
        distinction_coords = get_coords(umap_features, n_components=2)
        cause_effect_offset = cause_effect_offset[:2]

    else:
        distinction_coords = get_coords(umap_features)
    # Duplicate causes and effects so they can be plotted separately
    coords = np.empty(
        (distinction_coords.shape[0] * 2, distinction_coords.shape[1]),
        dtype=distinction_coords.dtype,
    )
    coords[0::2] = distinction_coords
    coords[1::2] = distinction_coords
    # Add a small offset to effects to separate them from causes
    coords[1::2] += cause_effect_offset

    # Purviews
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Extract vertex indices for plotly
    x, y = coords[:, 0], coords[:, 1]

    causes_x, causes_y, effects_x, effects_y = separate_cause_and_effect_for(coords)

    if order_on_z_axis:
        z = np.array([len(c.mechanism) for c in separated_ces])
    else:
        z = coords[:, 2]

    # This separates z-coordinates of cause and effect purviews
    causes_z, effects_z = separate_cause_and_effect_purviews_for(z)

    # Get node labels and indices for future use:
    node_labels = subsystem.node_labels
    node_indices = subsystem.node_indices

    # Get mechanism and purview labels
    mechanism_labels = list(map(label_mechanism, ces))
    mechanism_state_labels = [
        label_mechanism_state(subsystem, distinction) for distinction in ces
    ]
    purview_labels = list(map(label_purview, separated_ces))
    purview_state_labels = list(map(label_purview_state, separated_ces))

    (
        cause_purview_labels,
        effect_purview_labels,
    ) = separate_cause_and_effect_purviews_for(purview_labels)
    (
        cause_purview_state_labels,
        effect_purview_state_labels,
    ) = separate_cause_and_effect_purviews_for(purview_state_labels)

    mechanism_hovertext = list(map(hovertext_mechanism, ces))
    vertices_hovertext = list(map(hovertext_purview, separated_ces))
    causes_hovertext, effects_hovertext = separate_cause_and_effect_purviews_for(
        vertices_hovertext
    )

    # Make mechanism labels
    xm, ym, zm = (
        [c + cause_effect_offset[0] / 2 for c in x[::2]],
        y[::2],
        z[::2],
        # [n + (vertex_size_range[1] / 10 ** 3) for n in z[::2]],
    )
    labels_mechanisms_trace = go.Scatter3d(
        visible=show_mechanism_labels,
        x=xm,
        y=ym,
        z=[n + (vertex_size_range[1] / 10 ** 3 + mechanism_z_offset) for n in zm],
        mode="text",
        text=mechanism_labels,
        name="Mechanism Labels",
        showlegend=True,
        textfont=dict(size=mechanism_labels_size, color="black"),
        hoverinfo="text",
        hovertext=mechanism_hovertext,
        hoverlabel=dict(bgcolor="black", font_color="white"),
    )
    fig.add_trace(labels_mechanisms_trace)

    # Make mechanism state labels trace
    labels_mechanisms_state_trace = go.Scatter3d(
        visible=show_mechanism_labels,
        x=xm,
        y=ym,
        z=[
            n
            + (
                vertex_size_range[1] / 10 ** 3
                + mechanism_z_offset
                + state_label_z_offset
                + 0.01
            )
            for n in zm
        ],
        mode="text",
        text=mechanism_state_labels,
        name="Mechanism State Labels",
        showlegend=False,
        textfont=dict(size=state_labels_size, color="black"),
        hoverinfo="text",
        hovertext=mechanism_hovertext,
        hoverlabel=dict(bgcolor="black", font_color="white"),
    )
    fig.add_trace(labels_mechanisms_state_trace)

    # Compute purview and mechanism marker sizes
    purview_sizes = normalize_sizes(
        vertex_size_range[0], vertex_size_range[1], separated_ces
    )

    cause_purview_sizes, effect_purview_sizes = separate_cause_and_effect_purviews_for(
        purview_sizes
    )

    mechanism_sizes = [min(phis) for phis in chunk_list(purview_sizes, 2)]
    # Make mechanisms trace
    vertices_mechanisms_trace = go.Scatter3d(
        visible=show_vertices_mechanisms,
        x=xm,
        y=ym,
        z=[z + mechanism_z_offset for z in zm],
        mode="markers",
        name="Mechanisms",
        text=mechanism_labels,
        showlegend=True,
        marker=dict(size=mechanism_sizes, color="black"),
        hoverinfo="text",
        hovertext=mechanism_hovertext,
        hoverlabel=dict(bgcolor="black", font_color="white"),
    )
    fig.add_trace(vertices_mechanisms_trace)

    # Make cause purview labels trace
    labels_cause_purviews_trace = go.Scatter3d(
        visible=show_purview_labels,
        x=causes_x,
        y=causes_y,
        z=[n + (vertex_size_range[1] / 10 ** 3) for n in causes_z],
        mode="text",
        text=cause_purview_labels,
        name="Cause Purview Labels",
        showlegend=True,
        textfont=dict(size=purview_labels_size, color="red"),
        hoverinfo="text",
        hovertext=causes_hovertext,
        hoverlabel=dict(bgcolor="red"),
    )
    fig.add_trace(labels_cause_purviews_trace)

    # Make effect purview labels trace
    labels_effect_purviews_trace = go.Scatter3d(
        visible=show_purview_labels,
        x=effects_x,
        y=effects_y,
        z=[n + (vertex_size_range[1] / 10 ** 3) for n in effects_z],
        mode="text",
        text=effect_purview_labels,
        name="Effect Purview Labels",
        showlegend=True,
        textfont=dict(size=purview_labels_size, color="green"),
        hoverinfo="text",
        hovertext=causes_hovertext,
        hoverlabel=dict(bgcolor="green"),
    )
    fig.add_trace(labels_effect_purviews_trace)

    # Make cause purviews state labels trace
    labels_cause_purviews_state_trace = go.Scatter3d(
        visible=show_purview_labels,
        x=causes_x,
        y=causes_y,
        z=[
            n + (vertex_size_range[1] / 10 ** 3 + state_label_z_offset)
            for n in causes_z
        ],
        mode="text",
        text=cause_purview_state_labels,
        name="Cause Purview State Labels",
        showlegend=True,
        textfont=dict(size=state_labels_size, color="red"),
        hoverinfo="text",
        hovertext=causes_hovertext,
        hoverlabel=dict(bgcolor="red"),
    )
    fig.add_trace(labels_cause_purviews_state_trace)

    # Make effect purviews state labels trace
    labels_effect_purviews_state_trace = go.Scatter3d(
        visible=show_purview_labels,
        x=effects_x,
        y=effects_y,
        z=[
            n + (vertex_size_range[1] / 10 ** 3 + state_label_z_offset)
            for n in effects_z
        ],
        mode="text",
        text=effect_purview_state_labels,
        name="Effect Purview State Labels",
        showlegend=True,
        textfont=dict(size=state_labels_size, color="green"),
        hoverinfo="text",
        hovertext=effects_hovertext,
        hoverlabel=dict(bgcolor="green"),
    )
    fig.add_trace(labels_effect_purviews_state_trace)

    # Separating purview traces

    purview_phis = [purview.phi for purview in separated_ces]
    cause_purview_phis = []
    effect_purview_phis = []

    for i in range(len(purview_phis)):
        if i % 2 == 0:
            cause_purview_phis.append(purview_phis[i])
        else:
            effect_purview_phis.append(purview_phis[i])

    # direction_labels = list(flatten([["Cause", "Effect"] for c in ces]))
    vertices_cause_purviews_trace = go.Scatter3d(
        visible=show_vertices_purviews,
        x=causes_x,
        y=causes_y,
        z=causes_z,
        mode="markers",
        name="Cause Purviews",
        text=purview_labels,
        showlegend=True,
        marker=dict(size=cause_purview_sizes, color="red"),
        hoverinfo="text",
        hovertext=causes_hovertext,
        hoverlabel=dict(bgcolor="red"),
    )
    fig.add_trace(vertices_cause_purviews_trace)

    vertices_effect_purviews_trace = go.Scatter3d(
        visible=show_vertices_purviews,
        x=effects_x,
        y=effects_y,
        z=effects_z,
        mode="markers",
        name="Effect Purviews",
        text=purview_labels,
        showlegend=True,
        marker=dict(size=effect_purview_sizes, color="green"),
        hoverinfo="text",
        hovertext=effects_hovertext,
        hoverlabel=dict(bgcolor="green"),
    )
    fig.add_trace(vertices_effect_purviews_trace)

    # Initialize lists for legend
    legend_nodes = []
    legend_mechanisms = []
    legend_purviews = []
    legend_relation_purviews = []
    legend_mechanism_cause_purviews = []

    # 2-relations
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if show_edges:
        # Get edges from all relations
        edges = list(
            flatten(
                relation_vertex_indices(features, j)
                for j in range(features.shape[1])
                if features[:, j].sum() == 2
            )
        )
        if edges:
            # Convert to DataFrame
            edges = pd.DataFrame(
                dict(
                    x=x[edges],
                    y=y[edges],
                    z=z[edges],
                    line_group=flatten(
                        zip(range(len(edges) // 2), range(len(edges) // 2))
                    ),
                )
            )

            # Plot edges separately:
            two_relations = list(filter(lambda r: len(r.relata) == 2, relations))
            two_relations_grouped_and_indexed = purview_chunker(two_relations)
            two_relations_grouped_by_purview = two_relations_grouped_and_indexed[0]
            indexes_of_two_relations_grouped_by_purview = two_relations_grouped_and_indexed[
                1
            ]

            two_relations_sizes = normalize_sizes(
                edge_size_range[0], edge_size_range[1], two_relations
            )

            two_relations_coords = [
                list(chunk_list(list(edges["x"]), 2)),
                list(chunk_list(list(edges["y"]), 2)),
                list(chunk_list(list(edges["z"]), 2)),
            ]

            for r, relation in tqdm(
                enumerate(two_relations),
                desc="Computing edges",
                total=len(two_relations),
            ):
                relation_nodes = list(flatten(relation.mechanisms))
                relation_color = get_edge_color(relation, colorcode_2_relations)

                # Make node contexts traces and legendgroups
                if show_node_qfolds:
                    for node in node_indices:
                        node_label = make_label([node], node_labels)
                        if node in relation_nodes:

                            edge_two_relation_trace = go.Scatter3d(
                                visible=show_edges,
                                legendgroup=f"Node {node_label} q-fold",
                                showlegend=True if node not in legend_nodes else False,
                                x=two_relations_coords[0][r],
                                y=two_relations_coords[1][r],
                                z=two_relations_coords[2][r],
                                mode="lines",
                                name=f"Node {node_label} q-fold",
                                line_width=two_relations_sizes[r],
                                line_color=relation_color,
                                hoverinfo="text",
                                hovertext=hovertext_relation(relation),
                            )
                            fig.add_trace(edge_two_relation_trace)

                            if node not in legend_nodes:

                                legend_nodes.append(node)

                # Make mechanism contexts traces and legendgroups
                if show_mechanism_qfolds:
                    mechanisms_list = [distinction.mechanism for distinction in ces]
                    for mechanism in mechanisms_list:
                        mechanism_label = make_label(mechanism, node_labels)
                        if mechanism in relation.mechanisms:

                            edge_two_relation_trace = go.Scatter3d(
                                visible=show_edges,
                                legendgroup=f"Mechanism {mechanism_label} q-fold",
                                showlegend=True
                                if mechanism_label not in legend_mechanisms
                                else False,
                                x=two_relations_coords[0][r],
                                y=two_relations_coords[1][r],
                                z=two_relations_coords[2][r],
                                mode="lines",
                                name=f"Mechanism {mechanism_label} q-fold",
                                line_width=two_relations_sizes[r],
                                line_color=relation_color,
                                hoverinfo="text",
                                hovertext=hovertext_relation(relation),
                            )

                            fig.add_trace(edge_two_relation_trace)

                            if mechanism_label not in legend_mechanisms:

                                legend_mechanisms.append(mechanism_label)

                # Make compound purview contexts traces and legendgroups
                if show_compound_purview_qfolds:
                    purviews = list(relation.relata.purviews)

                    for purview in purviews:

                        purview_label = make_label(purview, node_labels)
                        edge_compound_purview_two_relation_trace = go.Scatter3d(
                            visible=show_edges,
                            legendgroup=f"Compound Purview {purview_label} q-fold",
                            showlegend=True
                            if purview_label not in legend_purviews
                            else False,
                            x=two_relations_coords[0][r],
                            y=two_relations_coords[1][r],
                            z=two_relations_coords[2][r],
                            mode="lines",
                            name=f"Compound Purview {purview_label} q-fold",
                            line_width=two_relations_sizes[r],
                            line_color=relation_color,
                            hoverinfo="text",
                            hovertext=hovertext_relation(relation),
                        )

                        fig.add_trace(edge_compound_purview_two_relation_trace)

                        if purview_label not in legend_purviews:
                            legend_purviews.append(purview_label)

                # Make relation purview contexts traces and legendgroups
                if show_relation_purview_qfolds:

                    # Just left this code to make sure if we need relation purviews for mechanisms. Probably not necessary anymore.
                    """for purview_group in indexes_of_two_relations_grouped_by_purview:
                        
                        for purview_index in purview_group:
                            index_in_group = purview_group.index(purview_index)
                            purview = (two_relations_grouped_by_purview[indexes_of_two_relations_grouped_by_purview.index(purview_group)][index_in_group]).purview
                            purview_label = make_label(purview, node_labels)
                            first_mechanism = two_relations[purview_group[0]].mechanisms[0]
                            first_mechanism_label = make_label(first_mechanism, node_labels)
                            
                            
                        
                            purview_group_index = indexes_of_two_relations_grouped_by_purview.index(purview_group)
                            whole_label = purview_label + mechanism_label + str(purview_group_index)
                            edge_two_relation_purview_trace = go.Scatter3d(
                                visible=show_edges,
                                legendgroup=f"Mechanism {first_mechanism_label} Relation Purview {purview_label} q-fold {purview_group_index}",
                                showlegend=True
                                if whole_label not in legend_relation_purviews      
                                else False,
                                x=two_relations_coords[0][purview_index],
                                y=two_relations_coords[1][purview_index],
                                z=two_relations_coords[2][purview_index],
                                mode="lines",
                                name=f"Mechanism {first_mechanism_label} Relation Purview {purview_label} q-fold {purview_group_index}",
                                line_width=two_relations_sizes[purview_index],
                                line_color=relation_color,
                                hoverinfo="text",
                                hovertext=hovertext_relation(two_relations[purview_index]),
                            )
                                
                            fig.add_trace(edge_two_relation_purview_trace)
                        
                            if whole_label not in legend_relation_purviews:

                                legend_relation_purviews.append(whole_label)"""

                    purview = relation.purview
                    purview_label = make_label(purview, node_labels)

                    edge_relation_purview_two_relation_trace = go.Scatter3d(
                        visible=show_edges,
                        legendgroup=f"Relation Purview {purview_label} q-fold",
                        showlegend=True
                        if purview_label not in legend_relation_purviews
                        else False,
                        x=two_relations_coords[0][r],
                        y=two_relations_coords[1][r],
                        z=two_relations_coords[2][r],
                        mode="lines",
                        name=f"Relation Purview {purview_label} q-fold",
                        line_width=two_relations_sizes[r],
                        line_color=relation_color,
                        hoverinfo="text",
                        hovertext=hovertext_relation(relation),
                    )

                    fig.add_trace(edge_relation_purview_two_relation_trace)

                    if purview_label not in legend_relation_purviews:
                        legend_relation_purviews.append(purview_label)

                # Make cause/effect purview per mechanism contexts traces and legendgroups
                if show_cause_per_mechanism_purview_qfolds:
                    # THIS PART IS TO BE FIXED. IT DOESN'T WORK.
                    # This is wrong. Don't do this.

                    distinctions_list = [distinction for distinction in ces]
                    for distinction in distinctions_list:
                        cause_purview = distinction.cause_purview
                        mechanism = distinction.mechanism
                        purview_label = make_label(cause_purview, node_labels)
                        mechanism_label = make_label(mechanism, node_labels)
                        mechanism_cause_purview_label = f"Mechanism {mechanism_label} Cause Purview {purview_label} q-fold"
                        if (
                            cause_purview in relation.relata.purviews
                            and mechanism in relation.mechanisms
                        ):

                            edge_cause_purviews_with_mechanisms_two_relation_trace = go.Scatter3d(
                                visible=show_edges,
                                legendgroup=mechanism_cause_purview_label,
                                showlegend=True
                                if mechanism_cause_purview_label
                                not in legend_mechanism_cause_purviews
                                else False,
                                x=two_relations_coords[0][r],
                                y=two_relations_coords[1][r],
                                z=two_relations_coords[2][r],
                                mode="lines",
                                name=mechanism_cause_purview_label,
                                line_width=two_relations_sizes[r],
                                line_color=relation_color,
                                hoverinfo="text",
                                hovertext=hovertext_relation(relation),
                            )

                            fig.add_trace(
                                edge_cause_purviews_with_mechanisms_two_relation_trace
                            )

                            if (
                                mechanism_cause_purview_label
                                not in legend_mechanism_cause_purviews
                            ):
                                legend_mechanism_cause_purviews.append(
                                    mechanism_cause_purview_label
                                )
                # Make all 2-relations traces and legendgroup
                edge_two_relation_trace = go.Scatter3d(
                    visible=show_edges,
                    legendgroup="All 2-Relations",
                    showlegend=True if r == 0 else False,
                    x=two_relations_coords[0][r],
                    y=two_relations_coords[1][r],
                    z=two_relations_coords[2][r],
                    mode="lines",
                    # name=label_relation(relation),
                    name="All 2-Relations",
                    line_width=two_relations_sizes[r],
                    line_color=relation_color,
                    hoverinfo="text",
                    hovertext=hovertext_relation(relation),
                )

                fig.add_trace(edge_two_relation_trace)

    # 3-relations
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Get triangles from all relations
    if show_mesh:
        triangles = [
            relation_vertex_indices(features, j)
            for j in range(features.shape[1])
            if features[:, j].sum() == 3
        ]

        if triangles:
            three_relations = list(filter(lambda r: len(r.relata) == 3, relations))
            three_relations_sizes = normalize_sizes(
                surface_size_range[0], surface_size_range[1], three_relations
            )
            # Extract triangle indices
            i, j, k = zip(*triangles)
            for r, triangle in tqdm(
                enumerate(triangles), desc="Computing triangles", total=len(triangles)
            ):
                relation = three_relations[r]
                relation_nodes = list(flatten(relation.mechanisms))

                if show_node_qfolds:
                    for node in node_indices:
                        node_label = make_label([node], node_labels)
                        if node in relation_nodes:
                            triangle_three_relation_trace = go.Mesh3d(
                                visible=show_mesh,
                                legendgroup=f"Node {node_label} q-fold",
                                showlegend=True if node not in legend_nodes else False,
                                # x, y, and z are the coordinates of vertices
                                x=x,
                                y=y,
                                z=z,
                                # i, j, and k are the vertices of triangles
                                i=[i[r]],
                                j=[j[r]],
                                k=[k[r]],
                                # Intensity of each vertex, which will be interpolated and color-coded
                                intensity=np.linspace(0, 1, len(x), endpoint=True),
                                opacity=three_relations_sizes[r],
                                colorscale="viridis",
                                showscale=False,
                                name=f"Node {node_label} q-fold",
                                hoverinfo="text",
                                hovertext=hovertext_relation(relation),
                            )
                            fig.add_trace(triangle_three_relation_trace)

                            if node not in legend_nodes:

                                legend_nodes.append(node)

                if show_mechanism_qfolds:
                    mechanisms_list = [distinction.mechanism for distinction in ces]
                    for mechanism in mechanisms_list:
                        mechanism_label = make_label(mechanism, node_labels)
                        if mechanism in relation.mechanisms:
                            triangle_three_relation_trace = go.Mesh3d(
                                visible=show_mesh,
                                legendgroup=f"Mechanism {mechanism_label} q-fold",
                                showlegend=True
                                if mechanism_label not in legend_mechanisms
                                else False,
                                # x, y, and z are the coordinates of vertices
                                x=x,
                                y=y,
                                z=z,
                                # i, j, and k are the vertices of triangles
                                i=[i[r]],
                                j=[j[r]],
                                k=[k[r]],
                                # Intensity of each vertex, which will be interpolated and color-coded
                                intensity=np.linspace(0, 1, len(x), endpoint=True),
                                opacity=three_relations_sizes[r],
                                colorscale="viridis",
                                showscale=False,
                                name=f"Mechanism {mechanism_label} q-fold",
                                hoverinfo="text",
                                hovertext=hovertext_relation(relation),
                            )
                            fig.add_trace(triangle_three_relation_trace)
                            if mechanism_label not in legend_mechanisms:
                                legend_mechanisms.append(mechanism_label)

                if show_compound_purview_qfolds:
                    purviews = list(relation.relata.purviews)

                    for purview in purviews:

                        purview_label = make_label(purview, node_labels)
                        edge_compound_purview_three_relation_trace = go.Mesh3d(
                            visible=show_edges,
                            legendgroup=f"Compound Purview {purview_label} q-fold",
                            showlegend=True
                            if purview_label not in legend_purviews
                            else False,
                            x=x,
                            y=y,
                            z=z,
                            i=[i[r]],
                            j=[j[r]],
                            k=[k[r]],
                            intensity=np.linspace(0, 1, len(x), endpoint=True),
                            opacity=three_relations_sizes[r],
                            colorscale="viridis",
                            showscale=False,
                            name=f"Compound Purview {purview_label} q-fold",
                            hoverinfo="text",
                            hovertext=hovertext_relation(relation),
                        )

                        fig.add_trace(edge_compound_purview_three_relation_trace)

                        if purview_label not in legend_purviews:
                            legend_purviews.append(purview_label)

                if show_relation_purview_qfolds:
                    purview = relation.purview
                    purview_label = make_label(purview, node_labels)

                    edge_relation_purview_three_relation_trace = go.Mesh3d(
                        visible=show_edges,
                        legendgroup=f"Relation Purview {purview_label} q-fold",
                        showlegend=True
                        if purview_label not in legend_relation_purviews
                        else False,
                        x=x,
                        y=y,
                        z=z,
                        i=[i[r]],
                        j=[j[r]],
                        k=[k[r]],
                        intensity=np.linspace(0, 1, len(x), endpoint=True),
                        opacity=three_relations_sizes[r],
                        colorscale="viridis",
                        showscale=False,
                        name=f"Relation Purview {purview_label} q-fold",
                        hoverinfo="text",
                        hovertext=hovertext_relation(relation),
                    )

                    fig.add_trace(edge_relation_purview_three_relation_trace)

                    if purview_label not in legend_relation_purviews:
                        legend_relation_purviews.append(purview_label)

                triangle_three_relation_trace = go.Mesh3d(
                    visible=show_mesh,
                    legendgroup="All 3-Relations",
                    showlegend=True if r == 0 else False,
                    # x, y, and z are the coordinates of vertices
                    x=x,
                    y=y,
                    z=z,
                    # i, j, and k are the vertices of triangles
                    i=[i[r]],
                    j=[j[r]],
                    k=[k[r]],
                    # Intensity of each vertex, which will be interpolated and color-coded
                    intensity=np.linspace(0, 1, len(x), endpoint=True),
                    opacity=three_relations_sizes[r],
                    colorscale="viridis",
                    showscale=False,
                    name="All 3-Relations",
                    hoverinfo="text",
                    hovertext=hovertext_relation(relation),
                )
                fig.add_trace(triangle_three_relation_trace)

        # Create figure
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    axes_range = [(min(d) - 1, max(d) + 1) for d in (x, y, z)]

    axes = [
        dict(
            showbackground=False,
            showline=False,
            zeroline=False,
            showgrid=show_grid,
            gridcolor="lightgray",
            showticklabels=False,
            showspikes=True,
            autorange=False,
            range=axes_range[dimension],
            backgroundcolor="white",
            title="",
        )
        for dimension in range(3)
    ]

    layout = go.Layout(
        showlegend=True,
        scene_xaxis=axes[0],
        scene_yaxis=axes[1],
        scene_zaxis=axes[2],
        scene_camera=dict(
            eye=dict(x=eye_coordinates[0], y=eye_coordinates[1], z=eye_coordinates[2])
        ),
        hovermode=hovermode,
        title=f"{network_name} Q-Structure",
        title_font_size=plot_title_size,
        legend=dict(
            title=dict(
                text="Trace legend (click trace to show/hide):",
                font=dict(color="black", size=legend_title_size),
            ),
            font_size=legend_font_size,
        ),
        autosize=autosize,
        height=plot_dimentions[0],
        width=plot_dimentions[1],
    )

    # Apply layout
    fig.layout = layout

    if show_causal_model:
        # Create system image
        save_digraph(subsystem, digraph_filename, layout=digraph_layout)
        encoded_image = base64.b64encode(open(digraph_filename, "rb").read())

        fig.add_layout_image(
            dict(
                name="Causal model",
                source="data:image/png;base64,{}".format(encoded_image.decode()),
                #         xref="paper", yref="paper",
                x=digraph_coords[0],
                y=digraph_coords[1],
                sizex=digraph_size[0],
                sizey=digraph_size[1],
                xanchor="left",
                yanchor="top",
            )
        )

        draft_template = go.layout.Template()
        draft_template.layout.annotations = [
            dict(
                name="Causal model",
                text="Causal model",
                opacity=1,
                font=dict(color="black", size=plot_title_size),
                xref="paper",
                yref="paper",
                x=digraph_coords[0],
                y=digraph_coords[1] + 0.05,
                xanchor="left",
                yanchor="bottom",
                showarrow=False,
            )
        ]

        fig.update_layout(
            margin=dict(l=left_margin),
            template=draft_template,
            annotations=[dict(templateitemname="Causal model", visible=True)],
        )

    if save_plot_to_html:
        plotly.io.write_html(fig, f"{network_name}_CES.html")
        fig.write_html("try.html")
    return fig
