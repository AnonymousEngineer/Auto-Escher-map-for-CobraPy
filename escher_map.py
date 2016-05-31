from __future__ import division, print_function
__author__ = 'JCThomas'

# TODO: informative error messages - largely done
# TODO: deal with double reactions
# TODO: if there's no need for a midnode don't put one in

import json
# Tend to use ordereddicts to make debugging easier
from collections import OrderedDict

#paff = 'C:/Users/JT/Dropbox/python/Metabolic model/'
#paff = 'C:/Users/JT/Dropbox/GBL/metabolic model/'
#paff_v = paff+'visualisations/'
#file_name = 'OPAL_model_standard_pathway_v1.xml'
node_id_counter, seg_id_counter, react_id_counter = 0, 0, 0
map_scale = 200 #required global
udlr_symbols = '^#<>' # Obsolete but various references to it still exist

class EscherMap():
    """Give a list of cobra reaction objects, a list of Metabolite objects.

    After the map object has been initialised with the required info use
    EM.generate_nodes_and_segments() then dump_json() to get the escher
    formated JSON.

    Reactions, Nodes, Segments are stored in dictionaries ('bins') by cobra ID
    """
    def __init__(self, cobra_model, cobra_reactions, met_list, tick):
        self.reactions = OrderedDict()
        self.reactions_by_name = OrderedDict()
        self.add_reactions(cobra_reactions)
        self.cobra_reactions = cobra_reactions
        self.cobra_model = cobra_model
        self.nodes = OrderedDict()
        self.segments = []
        met_occurence = {}
        for r in cobra_reactions:
            for m in r.metabolites:
                if m.id not in met_occurence.keys():
                    met_occurence[m.id]  = 1
                else:
                    met_occurence[m.id] += 1
        self.met_occurence = met_occurence

        #if type(met_list) is list
        self.met_list = met_list
        self.tick = tick # Uses the global
        self.node_by_grid = {} # populated when nodes are generated by Node.__init__()
        self.mapped_reactions = []


    def add_reactions(self, cobra_reactions):
        """Add a single reaction object or list of reactions."""
        if type(cobra_reactions) is not list:
            cobra_reactions = [cobra_reactions]
        for r in cobra_reactions:
            react_obj = EscherReaction(r.id,None,r.id)
            # Add metabolites to reaction
            for metabolite in r.metabolites:
                react_obj.add_metabolite(metabolite.id, r.metabolites[metabolite])
            self.reactions[react_obj.id] = react_obj
            self.reactions_by_name[r.id] = react_obj

    def get_reaction_by_metabolites(self, met1, met2, distal_met = None):
        """Returns a reaction that has in common metabolite names met1 and
        met2. Distal_met is required for common metabolites that are connected
        to sidenodes"""
        # segments require reaction id
        current_reaction = [self.reactions[r] for r in self.reactions
                            if met1 in self.reactions[r].metabolites
                            and met2 in self.reactions[r].metabolites
                            and r not in self.mapped_reactions]
        if distal_met:
            current_reaction = [r for r in current_reaction if distal_met
                                in r.metabolites]

        if len(current_reaction) == 1:
            current_reaction = current_reaction[0]
            #print(current_reaction)

        elif len(current_reaction) == 0:
            print('False metabolite connection made', met1, met2)
            input('Press enter to crash')
            raise ValueError

        else:

            current_reaction = [r for r in current_reaction if
                                r.metabolites[met1] < 0 < r.metabolites[met2]]

            # if len(current_reaction) > 1:
            #     print([r.name for r in current_reaction])
            #     print([r.metabolites for r in current_reaction])
            #     print('multiple valid reactions found', met1, met2)
            if not current_reaction:
                print(met1, met2)
                print([r.name for r in current_reaction])
                print([r.metabolites for r in current_reaction])
                print("can't pick a reaction")
                raise ValueError

        return current_reaction

    def generate_nodes_and_segments(self):#, selective_midnode_placement = True):
        """Takes reactions and a list of Metabolite objects, met_list,
         and generates nodes and segments and labels for the map.
         Call map.dump_json to get the Escher formatted file.
        """
        global node_id_counter
        tick = self.tick
        # Go through the grid creating nodes and populating met_bin
        for met in self.met_list:
            if type(self.met_list) is dict:
                met = self.met_list[met]

            if met is not None:
                # print(met.name)
                # print(met.cobra_obj)
                metxy = tuple([n*tick for n in met.grid_xy])
                x, y = metxy
                labxy = x+20, y-20
                #print(met, metxy)
                if not met.connections:
                    met.connections = []

                EscherNode(
                    id_num = met.node_id,
                    name = met.name,
                    bigg_id = met.name,
                    xy=metxy,
                    labelxy=labxy,
                    connections = met.connections,
                    cobra_metabolite=met.cobra_obj,
                    grid_xy=met.grid_xy,
                    primary = met.primary,
                    escher_map=self,
                    #target_reaction = met.target_reaction
                )
        # Not implemented
        # if selective_midnode_placement:
        #     requires_midnodes = []
        #     for n in self.nodes.values():
        #         if n.connections:
        #             for conn in n.connections:
        #                 if not conn.direct: # Indirect
        #                     # a tuple that is the node and reaction that does not require midnodes
        #                     requires_midnodes.append((self.nodes[conn.node_id], conn.reaction_name))
        # else:
        #     requires_midnodes = False

        for node in self.nodes.values():
            # Go through metabolite nodes generating segments and mid nodes
            # where connections are direct, and just segments where they are not
            # First do direct connections

            if node.connections:
                for connect in node.connections:
                    if connect.direct: # not to midnode, it's a connection between non-common metabolites
                        # Create midnodes equidistant from two metabolite nodes
                        # Get the grid coords we are spanning

                        start = node.grid_xy
                        if type(connect.node_id) is str:
                            end_node = self.nodes[connect.node_id]
                        else:
                            try:
                                end_node = self.node_by_grid[(connect[0], connect[1])]
                            except KeyError:
                                print(node.name, node.id, 'seeks non-existant node at', connect,
                                      '\nIf its a sink reaction with no product or only involves \
common metabolites then no worries')

                                end_node = None
                        if end_node:
                            end = end_node.grid_xy

                            current_reactions = connect.reaction_name

                            if type(current_reactions) is not list:
                                current_reactions = [current_reactions]

                            for reaction_number, current_reaction in enumerate(current_reactions):
                                # If the reaction is not in "requires_midnodes" then the actual midnode creation step
                                # is skipped, and the connection line is different. Otherwise it proceedes the same
                                #Create midnodes, connect metabolites to them and record midmaker ids in node
                                mm_node_pair = [] # Where the new midnodes get put
                                midmid = (0,0) #Used to place the reaction label, becomes the mean xy of the mid markers

                                # m is used both to indicate the current node being process and to
                                # place the midmarkers 1/3 or 2/3 of the way between the main markers
                                for m in (1,2):
                                    # Select node to which we are adding midmarker locations to
                                    current_node = [None, node, end_node][m]
                                    #distal_metabolite  = [None, end_node, node][m]
                                    mmxy = []

                                    # Get the one-third mid marker's xy coords between the node and end_node
                                    for n in (0,1):
                                        mmxy.append(
                                            (start[n]+((end[n]-start[n])/3)*m)*tick+10*reaction_number
                                        )

                                    #raw_input()
                                    mmxy = tuple(mmxy)
                                    midmid = add_tup(midmid, mmxy)

                                    idnum = 'mm'+str(node_id_counter)
                                    r_id = self.reactions_by_name[current_reaction].id

                                    node_id_counter +=1
                                    midmarker = EscherNode('','',idnum,'midmarker', xy = mmxy,
                                                           escher_map=self, primary = False)


                                    midmarker.connect(r_id, current_node.id, self)
                                    mm_node_pair.append(midmarker)

                                    # store mid marker locations in the local node
                                    # need to work out direction from node xys

                                    udlr = udlr_symbols

                                    ## MOSTLY OBSOLETE replaced |direction| with |reaction| as way of
                                    ## identifying segments, but the label_xy adjustment still useful
                                    ## though it only really works with fully | or - lines
                                    #Determine direction of  connection
                                    # Detect and fix diaganal connections... I'm pretty sure just
                                    # pretending its actually one or the other should be fine since the
                                    # code can now deal with multiple reactions in the same direction,
                                    # so moving the start down a little, but not chainging the grid xy
                                    # to match
                                    xy_dif = tuple([start[i] - end[i] for i in (0, 1)])
                                    if abs(xy_dif[0])==abs(xy_dif[1]):
                                        start = (start[0], start[1]+0.1)
                                        xy_dif = tuple([start[i] - end[i] for i in (0, 1)])

                                    # If it moves further vertically:
                                    if abs(xy_dif[0])<abs(xy_dif[1]):
                                        direction_grid = [
                                            [udlr[1],udlr[0]],
                                            [udlr[0],udlr[1]]
                                        ]
                                        direction = direction_grid[xy_dif[1]>0][m-1]
                                        reaction_label_xy = (20,0)

                                    # If it's a horizontal connection
                                    elif abs(xy_dif[0])>abs(xy_dif[1]):
                                        direction_grid = [
                                        [udlr[3],udlr[2]],
                                        [udlr[2],udlr[3]]
                                        ]
                                        direction =direction_grid[xy_dif[0]>0][m-1]
                                        reaction_label_xy = (0,-30)

                                    # # Add midmarker location to relevent node
                                    current_node.midmarkers[current_reaction] = midmarker.id

                                    # while len(current_node.midmarkers) < reaction_number+1:
                                    #     current_node.midmarkers.append({})
                                    #     current_node.reactions_partook.append({})
                                    # current_node.midmarkers[reaction_number][direction] = midmarker.id
                                    # current_node.reactions_partook[reaction_number][direction] = current_reaction


                                # Create the segment connecting the midnodes
                                mm1, mm2 = mm_node_pair
                                r_id = self.reactions_by_name[current_reaction].id
                                mm1.connect(r_id, mm2.id, self)

                                # Place the reaction label
                                midmid = (midmid[0]/2, midmid[1]/2)

                                reaction_label_xy = add_tup(reaction_label_xy, midmid)
                                reaction_label_xy = add_tup(reaction_label_xy,
                                                            (10*reaction_number, 10*reaction_number))
                                self.reactions_by_name[current_reaction].label_xy\
                                    = reaction_label_xy

        # Now connect the side metabolites to midnodes
        for node in self.nodes.values():
            if node.connections:
                for connect in node.connections:
                    if not connect.direct: # Connects to midnode
                        if type(connect.node_id) is str:
                            end_node = self.nodes[connect.node_id]
                        else:
                            end_node = self.node_by_grid[(connect[0], connect[1])]
                        current_reaction = connect.reaction_name
                        target_node_id = end_node.midmarkers[current_reaction]

                        if type(current_reaction) is not list:
                            current_reaction = [current_reaction]
                            for react in current_reaction:
                                r_id = self.reactions_by_name[react].id
                                node.connect(r_id,target_node_id,self)


    def dump_json(self, file_name = '', print_json = False):
        """Return a JSON format string that can be used to draw
         an Escher map. Will be written to file if file_name is specified."""
        nodes_json = {}
        for node_id in self.nodes:
            nodes_json[node_id] = self.nodes[node_id].get_json()
        reaction_json = {}
        for reaction_id in self.reactions:
            reaction_json[reaction_id] = self.reactions[reaction_id].get_json()

        hix, lowx, hiy, lowy = 0, 0, 0, 0
        for n in self.nodes.values():
            nx, ny = n.xy
            hix = nx if nx > hix else hix
            lowx = nx if nx < lowx else lowx
            hiy = ny if ny > hiy else hiy
            lowy = ny if ny < lowy else lowy

        canvas_xy = (40+hix-lowx, 40+hiy-lowy)

        canvas_offset = (lowx-20, lowy-20)
        jd = {
            "reactions":reaction_json,
            "nodes":nodes_json,
            "membranes":[],
            "text_labels":{},
            "canvas":{"x":canvas_offset[0], "y":canvas_offset[1],
                      "width":canvas_xy[0],"height":canvas_xy[1]}
        }

        js = json.dumps(jd)
        if print_json:
            print(js)
        if file_name:
            with open(file_name, 'w') as f:
                f.write(js)
        return js


class EscherNode():
    """A point in the map. Can be a metabolite or just where two lines (segments) join.
    node_types seen "metabolite","midmarker","multimarker".
    Only "metabolite" seems important to the renderer.
    biggid is displayed on the map if given. ID must be unique and is auto assigned.

    Primary = False makes the metabolite circle smaller. If the node's not
    a metabolite it doesnt appear to do anything.

    .midmarkers used by EM.generate_nodes_and_segments()

    .connect() creates segments and updates all ENode and EReaction objects.

    Created by EM.generate_nodes_and_segments()
    """
    def __init__(self,  name = None, bigg_id="", id_num = None,
                 n_type = "metabolite", labelxy = (0,0), xy = (0,0),grid_xy = None,
                 connections = None, cobra_metabolite = None, primary = True,
                 escher_map = None):
        global node_id_counter
        self.xy = xy
        if grid_xy is not None:
            self.grid_xy = grid_xy
        if id_num is None:
            id_num = "n"+str(node_id_counter)
            node_id_counter +=1
        if name is None:
            name = id_num
        if labelxy is None:
            self.label_xy = xy
        #self.distal_node = distal_node

        self.connections = connections if not None else []

        if cobra_metabolite is not None:
            self.cobra_metabolite = cobra_metabolite
        if escher_map is not None:
            if grid_xy is not None and grid_xy not in escher_map.node_by_grid.keys():
                escher_map.node_by_grid[grid_xy] = self
            elif grid_xy is None and n_type != 'midmarker':
                print('Node not added (no grid_xy)', bigg_id, n_type)
            elif grid_xy in escher_map.node_by_grid.keys():
                exant_node_name = escher_map.node_by_grid[grid_xy].name
                errorstring = 'Two metabolites on the same grid reference: %s, %s. Grid %s'%(
                    name, exant_node_name, grid_xy
                )
                raise ValueError(errorstring)
            #print(grid_xy)
            escher_map.nodes[id_num] = self
        self.node_is_primary = primary
        # if gridxy is not None:
        #     self.gridxy = gridxy
        self.id = str(id_num)
        self.node_type = n_type
        self.name = name
        self.bigg_id = bigg_id
        self.x, self.y = xy
        self.label_x, self.label_y = labelxy
        self.connected_segments = []

        # The ID of midmarker nodes indexed by the reaction they are associated with
        self.midmarkers = {}


    def connect(self, reaction_id, to_node_id, escher_map):
        """Pass the ID numbers to make a connection, a segment is
        generated and added to self.reactions and a reference to the
        new segment is added to the target node."""
        seg = EscherSegment(to_node_id, self.id)
        #print(self.id, {"reaction_id":str(reaction_id),"segment_id":seg.id})
        self.connected_segments.append({"reaction_id":str(reaction_id),"segment_id":str(seg.id)})
        escher_map.nodes[to_node_id].connected_segments.append({"reaction_id":str(reaction_id),"segment_id":str(seg.id)})
        escher_map.reactions[reaction_id].add_segments(seg)

    def get_json(self):

        jd = {"node_type":self.node_type,
        "connected_segments":self.connected_segments,
        "node_is_primary":self.node_is_primary,
        "label_x":self.label_x,
        "label_y":self.label_y,
        "name":self.name,
        "x":self.x,
        "y":self.y,
        "bigg_id":self.bigg_id}

        return jd

    def __repr__(self):

        type_ = self.bigg_id if self.bigg_id else self.node_type

        s = "<EscherNode %s: %s %s>"%(
            self.id, type_, self.xy
        )
        return s


class EscherReaction():
    """Define a reaction. ID should be unique. Name matches the
    ID in the COBRA model.
    Bigg_id gets printed on the map.
    Metabolites in form of {"cobra_met_id":int_coefficent}
    Labelxy refers to the absolute position of the label.
    """
    def __init__(self,  name, r_id = None, bigg_id = "unnamed", metabolites = None,
                 label_xy = (0,0), reversibility = True):
        global react_id_counter
        self.name = name
        if r_id is None:
            r_id = 'r'+str(react_id_counter)
            react_id_counter+=1
        if metabolites is None:
            metabolites = {}
        self.id = r_id
        self.bigg_id = bigg_id
        self.metabolites = metabolites
        self.segments = {}

        self.label_xy =  label_xy
        self.reversibility = reversibility
        # if cobra_r  is not None:
        #     self.cobra_r = cobra_r
        #react_bin[self.name] = self

    def add_segments_by_id(self, segment_ids, map_obj):
        """Pass a segment id, or list of segment ids and the
        segment object is added to the dictionary.
        """
        if type(segment_ids) is not list:
            segment_ids = [segment_ids]
        for seg in segment_ids:
            self.segments[seg] = map_obj.segments[seg].get_json()

    def add_segments(self, segments):
        if type(segments) is not list:
            segments = [segments]
        for seg in segments:
            self.segments[seg.id] = seg.get_json()

    def add_metabolite(self, name, coefficient):
        self.metabolites[name] = coefficient

    def get_json(self):
        json_metabolites = {}
        for m in self.metabolites:
            json_metabolites[m] = {"coefficient":self.metabolites[m]}

        label_x, label_y = self.label_xy
        label_y = label_y
        jd = \
        {
            "name":self.name,
            "bigg_id":self.bigg_id,
            "segments":self.segments,
            "reversibility":self.reversibility,
            "metabolites":json_metabolites,
            "label_x":label_x,
            "label_y":label_y
        }
        return jd

    def __str__(self):
        met = str(self.metabolites)
        return "Reaction {name} ({id}): {met}".format(
            name = self.name, id = self.id, met = met
        )

class EscherSegment:
    """A line on the map. Requires to and from node IDs.
    Give b1 and b2 values to curve the line as (x, y).
    Segments get added to EReactions using ER.add_segment"""
    def __init__(self, to_node, from_node, id_num = None, b1 = None, b2 = None):
        global seg_id_counter
        if id_num is None:
            id_num = 's'+str(seg_id_counter)
            seg_id_counter+=1
        self.id = id_num
        self.to_node_id = to_node
        self.from_node_id = from_node
        self.b1, self.b2 = b1, b2
        #seg_bin[self.id] = self

    def get_json(self):
        """Return a dictionary representation of the node that can be
        used to generate a JSON"""
        jd = \
            {"to_node_id":self.to_node_id,
            "b1":self.b1,"b2":self.b2,
            "from_node_id":self.from_node_id}

        return jd

class Metabolite():
    """To hold node and metabolite info before it gets passed to Node objects
    when processed by EscherMap.generate_nodes_and_segments(). Connects
    expected in the format:
    [(target1x, target1y, direct, reaction_name), (target2x, etc)]
    OR [(target_node_id, None, direct, reaction_name)]
    the xy of targets being the grid reference
    """
    def __init__(self, name, node_id, cobra_obj, grid_xy = None,
                 grid_string = None, primary = True, ):
        # Assign all required arguments
        self.name, self.node_id, self.cobra_obj\
            = name, node_id, cobra_obj
        self.connections = []
        self.__troof_strings = []
        if grid_string:
            self.grid_string = grid_string
        self.grid_xy = grid_xy

        self.primary = primary

    def __str__(self):
        id_s = "%s [%s]"%(self.cobra_obj.name, self.cobra_obj.id)
        x, y = self.grid_xy  if self.grid_xy else ('_', '_')
        conn = [(con.met_name, con.reaction_name) for con in self.connections]
        return "{}: ({},{}). Cnx: {}".format(id_s, x, y, conn)

    def __repr__(self):
        s = self.__str__()
        return "<{s}>".format(s)

    def add_connection(self,node_id = None, met_name = None,
                     direct = True, reaction_name = None):
        """Test if the connection has already been made and add it if not"""
        new_conn = self.Connection(node_id, met_name, direct, reaction_name)
        if new_conn._troof not in self.__troof_strings:
            self.connections.append(new_conn)
            self.__troof_strings.append(new_conn._troof)

    class Connection:
        def __init__(self, node_id = None, met_name = None,
                     direct = True, reaction_name = None):
            self.node_id, self.met_name, self.direct, self.reaction_name\
            = node_id, met_name, direct, reaction_name

        @property
        def _troof(self):
            """Used to avoid duplicate reactions"""
            return '~'.join([
                str(att) for att in (self.node_id, self.met_name, self.direct, self.reaction_name)
            ])


def add_tup(tup1, tup2):
    sum_tup = [0, 0]
    for i in (0, 1):
        sum_tup[i] += tup1[i] +tup2[i]
    return tuple(sum_tup)

def get_xy(anarray):
    """Return a dictionary of grid references (x,y) from a 2-D array"""
    grid_refs = {}
    for rowi, row in enumerate(anarray):
        for coli, cell in enumerate(row):
            grid_refs[cell] = (coli, rowi)
    return grid_refs

# def get_coords_from_cell_ref(cell_name):
#     """return grid ref as tuple (x, y), give excel style grid string
#     eg 'C5' or 'AA20'"""
#
#     con_x, con_y = 1, 0
#     # seperate the letter and number portion of the string
#     col_string, num_string = '' ,''
#     for char in cell_name:
#         if char.isalpha():
#             col_string += char
#         elif char.isdigit():
#             num_string+=char
#     try: # If the string does not have a number in it this causes an exception
#         y = int(num_string)
#     except ValueError:
#         # Return so that an informative error can be generated
#         return None
#     # The columns in excel are numbered in base 26 essentially
#     col_string = col_string.lower()
#     col_nums = [ord(c)-96 for c in col_string]
#     col_nums.reverse()
#     #col_nums = [col_nums[i]*26**i for i in range(len(col_nums))]
#     for i in range(len(col_nums)):
#         col_nums[i] = col_nums[i]*26**i
#     x = sum(col_nums)
#     # zero-indxing
#     x, y = x-1, y-1
#     return x,y

# def write_excel_map(file_path, mets):
#     import xlwt
#     # Take grid_xy of met objects, write em to an excel file
#     # metname:connect_string

# def process_metabolite_grid(met_grid, cobra_model, return_list =  True, return_dict = False):
#     """THIS WON'T WORK ANYMORE.
#     Take an array of metabolite names that refer to the cobra_model.metabolites.id
#     and return a flat list of Metabolite objects with connections.
#     Alters global var map_scale based on first cell."""
#     global node_id_counter, map_scale
#     flat_list = []
#     for rowi, row in enumerate(met_grid):
#         #print(rowi, row)
#         for coli, met in enumerate(row):
#             # First cell is the tick value
#             if rowi == 0 and coli == 0:
#                 try:
#                     map_scale = int(met)
#                 except ValueError:
#                     print('First cell (A1) can be used to adjust scale.\nUsing default of 150.')
#                     map_scale = 150
#                 met = None
#             if met is not None and met != '':
#                 # First create the metabolite list recording the metabolite names they connect to
#                 # and populate the metabolite flat list. Then go through the flat list getting
#                 # the grid references of connections
#
#                 # Check it specifies a connect to something else, connections specified in one direction only.
#                 if ':' in met:
#                     connects_list = []
#                     met, connects = met.split(':')
#                     connects = connects.split(',')
#                     # Con is the name of the metabolite connected to
#                     for con in connects:
#                         if con[0] in udlr_symbols:
#                             direction = con[0]
#                             con = con[1:]
#                         else:
#                             direction = False
#                     connects_list.append((con, direction))
#                 else:
#                     connects_list = None
#
#                 grid_ref = (coli, rowi)
#                 node_name = 'n'+str(node_id_counter)
#                 node_id_counter += 1
#                 cobra_obj = cobra_model.metabolites.get_by_id(met)
#                 flat_list.append( Metabolite(met, node_name, cobra_obj, grid_ref,connects_list) )
#
#     flat_list_names = [m.name for m in flat_list]
#     # Go through metabolite list changing metabolite connections from names to grid refs
#     for met in flat_list:
#         if met.connections:
#             grid_refs = []
#             for con in met.connections:
#                 target_name = con[0]
#                 direction = con[1]
#                 # Find all matching names
#                 loc_of_name_matches = []
#                 for i, name in enumerate(flat_list_names):
#                     if name == target_name:
#                         loc_of_name_matches.append(flat_list[i].grid_xy)
#                 # Which one's closest
#                 match_distances = []
#                 for m in loc_of_name_matches:
#                     x1, y1, = m
#                     x2, y2 = met.grid_xy
#                     match_distances.append(abs(x1-x2)+abs(y1-y2))
#                     nearest = loc_of_name_matches[match_distances.index(min(match_distances))]
#                 if loc_of_name_matches:
#                     tx, ty = nearest
#                 # If the name is not in the list try treating it as an excel cell name
#                 else:
#                     txy = get_coords_from_cell_ref(con[0])
#                     if txy is not None:
#                         tx, ty = txy
#                     else:
#                         s = ''.join(['Metabolite at grid ref ', str(met.grid_xy), ' named ', met.name,
#                               ' links to non-existant metabolite/cell "', con[0]+'".'])
#                         raise ValueError(s)
#
#                 connection = (tx, ty, direction)
#
#                 grid_refs.append(connection)
#             met.connections = grid_refs
#
#     if return_dict:
#         d = {}
#         keys = [m.grid_xy for m in flat_list]
#         for n,k in enumerate(keys):
#             d[k] = flat_list[n]
#     if return_list and return_dict:
#         return flat_list, d
#     if return_list: return flat_list
#     if return_dict: return d







