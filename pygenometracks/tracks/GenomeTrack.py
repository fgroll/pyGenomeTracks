# -*- coding: utf-8 -*-

from .. utilities import to_string, to_bytes, InputError, transform
import logging
import numpy as np
from matplotlib import colors as mc
import matplotlib.pyplot as plt
from matplotlib.ticker import LogFormatter
import re

# This is a regex for float which would work for 11, 102.25, but also .2
float_regex = r'(?:\d+)?(?:\.\d+)?'
# This is a regex for color_tuple without space: (float,float,float) which
# put each float in a group:
color_tuple = re.compile(r'^\(({0}),({0}),({0})\)$'.format(float_regex))
# This is a regex for group without comma except between parenthesis
block_no_comma_outside_parenthesis = re.compile(r'(?:[^,(]|\([^)]*\))+')


class GenomeTrack(object):
    """
    The GenomeTrack object is a holder for all tracks that are to be plotted.
    For example, to plot a bedgraph file a new class that extends GenomeTrack
    should be created.

    It is expected that all GenomeTrack objects have a plot method.

    """
    SUPORTED_ENDINGS = []
    TRACK_TYPE = None
    OPTIONS_TXT = """
# title of track (plotted on the right side)
title =
# height of track in cm (ignored if the track is overlay on top the previous track)
height = 2
# if you want to plot the track upside-down:
# orientation = inverted
# if you want to plot the track on top of the previous track. Options are 'yes' or 'share-y'.
# For the 'share-y' option the y axis values is shared between this plot and the overlay plot.
# Otherwise, each plot use its own scale
#overlay_previous = yes
"""
    DEFAULTS_PROPERTIES = {}
    NECESSARY_PROPERTIES = []
    SYNONYMOUS_PROPERTIES = {}
    POSSIBLE_PROPERTIES = {}
    BOOLEAN_PROPERTIES = []
    STRING_PROPERTIES = ['file_type', 'orientation',  # For XAxisTrack and SpacerTrack these 2 are not used
                         'overlay_previous', 'title']
    FLOAT_PROPERTIES = {'height': [0, np.inf]}
    INTEGER_PROPERTIES = {}

    def __init__(self, properties_dict):
        FORMAT = "[%(levelname)s:%(filename)s:%(lineno)s - %(funcName)20s()] %(message)s"
        logging.basicConfig(format=FORMAT)
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
        self.log = log
        self.properties = properties_dict
        self.set_properties_defaults()
        self.file_type = 'test'

    def set_properties_defaults(self):
        # put to default all properties which are not set:
        for prop in self.DEFAULTS_PROPERTIES:
            if prop not in self.properties:
                self.properties[prop] = self.DEFAULTS_PROPERTIES[prop]
        # check if properties are possible:
        for prop in self.POSSIBLE_PROPERTIES:
            possibles = self.POSSIBLE_PROPERTIES[prop]
            if self.properties[prop] not in possibles:
                default_value = self.DEFAULTS_PROPERTIES[prop]
                self.log.warning(f"*WARNING* {prop}: '{self.properties[prop]}'"
                                 " for section "
                                 f"{self.properties['section_name']}"
                                 f" is not valid. {prop} has "
                                 "been set to "
                                 f"{default_value}.\n")
                self.properties[prop] = default_value

    def plot_y_axis(self, ax, plot_axis, transform='no', log_pseudocount=0,
                    y_axis='tranformed', only_at_ticks=False):
        """
        Plot the scale of the y axis with respect to the plot_axis
        Args:
            ax: axis to use to plot the scale
            plot_axis: the reference axis to get the max and min.
            transform: what was the transformation of the data
            log_pseudocount:
            y_axis: 'tranformed' or 'original'
            only_at_ticks: False: only min_max are diplayed
                           True: only ticks values are displayed

        Returns:

        """
        if not self.properties.get('show_data_range', True):
            return

        def value_to_str(value):
            # given a numeric value, returns a
            # string that removes unneeded decimal places
            if value % 1 == 0:
                str_value = str(int(value))
            else:
                str_value = f"{value:.1f}"
            return str_value

        def untransform(value, transform, log_pseudocount):
            # given a numeric value, transform and log_pseudocount
            # return the value before the transformation
            if transform == 'log':
                return np.exp(value) - log_pseudocount
            elif transform == 'log2':
                return np.exp2(value) - log_pseudocount
            elif transform == 'log10':
                return np.power(10, value) - log_pseudocount
            elif transform == 'log1p':
                return np.expm1(value)
            elif transform == '-log':
                return np.exp(- value) - log_pseudocount

        ymin, ymax = plot_axis.get_ylim()
        # If the ticks are closer than epsilon from the top or bottom
        # The vertical alignment of label is adjusted
        epsilon = (ymax - ymin) / 100
        # When the ymax and ymin are plotted (when there is no grid)
        # The tick is shifted inside of epsilon_pretty
        # To avoid to have only half of the width of the line plotted
        epsilon_pretty = epsilon

        if only_at_ticks:
            # plot something that looks like this:
            # tick3 ┐
            #       │
            # tick2-|
            #       │
            # tick1 ┘
            if ymin < ymax:
                ticks_values = [t for t in plot_axis.get_yticks() if t <= ymax and t >= ymin]
            else:
                ticks_values = [t for t in plot_axis.get_yticks() if t >= ymax and t <= ymin]
                ticks_values.sort(reverse=True)
            labels_pos = ticks_values
            if transform == 'no' or y_axis == 'transformed':
                ticks_labels = [value_to_str(t) for t in ticks_values]
            else:
                # There is a transformation and we want to display original values
                ticks_labels = [value_to_str(untransform(t, transform, log_pseudocount)) for t in ticks_values]
        elif transform == 'no' or y_axis == 'transformed':
            # This is a linear scale
            # plot something that looks like this:
            # ymax ┐
            #      │
            #      │
            # ymin ┘
            # adjust the positions such that the lines are plotted complete
            # and not only half of the width of the line.
            ticks_values = [ymin + epsilon_pretty, ymax - epsilon_pretty]
            labels_pos = [ymin, ymax]
            ticks_labels = [value_to_str(v) for v in [ymin, ymax]]
            if y_axis == 'transformed' and transform != 'no':
                if transform == 'log1p':
                    ymid_str = "log(1 + x)"
                else:
                    if log_pseudocount == 0:
                        ymid_str = f"{transform}(x)"
                    else:
                        ymid_str = f"{transform}({log_pseudocount} + x)"

                ax.text(0, (ymax + ymin) / 2, ymid_str,
                        verticalalignment='center',
                        horizontalalignment='right', wrap=True)
        else:
            # There is a transformation and we want to display original values
            if ymin * ymax < 0:
                ymid = 0
            else:
                ymid = (ymin + ymax) / 2
            # plot something that looks like this:
            # ymax ┐
            #      │
            # ymid-|
            #      │
            # ymin ┘
            ticks_values = [ymin + epsilon_pretty, ymid, ymax - epsilon_pretty]
            labels_pos = [ymin, ymid, ymax]
            ticks_labels = [value_to_str(untransform(v, transform, log_pseudocount)) for v in [ymin, ymid, ymax]]

        # The lower label should be verticalalignment='bottom'
        # if it corresponds to ymin
        i = 0
        if (ymin < ymax and ticks_values[i] <= ymin + epsilon) \
           or (ymin > ymax and ticks_values[i] >= ymin + epsilon):
            v_al = 'bottom'
            adjusted_value = labels_pos[i] - epsilon
        else:
            v_al = 'center'
            adjusted_value = labels_pos[i]
        ax.text(-0.2, adjusted_value, ticks_labels[i],
                verticalalignment=v_al, horizontalalignment='right')
        x_pos = [0, 0.5]
        y_pos = [ticks_values[i]] * 2
        for i in range(1, len(ticks_values) - 1):
            ax.text(-0.2, labels_pos[i], ticks_labels[i],
                    verticalalignment='center',
                    horizontalalignment='right')
            x_pos += [0.5, 0, 0.5]
            y_pos += [ticks_values[i]] * 3

        # The upper label should be verticalalignment='top'
        # if it corresponds to ymax
        i = len(ticks_values) - 1
        if (ymin < ymax and ticks_values[i] >= ymax - epsilon) \
           or (ymin > ymax and ticks_values[i] <= ymax - epsilon):
            v_al = 'top'
        else:
            v_al = 'center'
        ax.text(-0.2, labels_pos[i], ticks_labels[i],
                verticalalignment=v_al, horizontalalignment='right')
        x_pos += [0.5, 0]
        y_pos += [ticks_values[i]] * 2

        # Finally plot the line:
        ax.plot(x_pos, y_pos, color='black', linewidth=1)

        # Set the lims:
        ax.set_ylim(plot_axis.get_ylim())
        ax.set_xlim(0, 1)
        ax.patch.set_visible(False)

    def plot_label(self, label_ax, width_dpi, h_align='left'):
        if h_align == 'left':
            label_ax.text(0.05, 0.5, self.properties['title'],
                          horizontalalignment='left', size='large',
                          verticalalignment='center',
                          transform=label_ax.transAxes,
                          wrap=True)
        elif h_align == 'right':
            txt = label_ax.text(1, 0.5, self.properties['title'],
                                horizontalalignment='right', size='large',
                                verticalalignment='center',
                                transform=label_ax.transAxes,
                                wrap=True)
            # To be able to wrap to the left:
            txt._get_wrap_line_width = lambda: width_dpi
        else:
            txt = label_ax.text(0.5, 0.5, self.properties['title'],
                                horizontalalignment='center', size='large',
                                verticalalignment='center',
                                transform=label_ax.transAxes,
                                wrap=True)
            # To be able to wrap to the left:
            txt._get_wrap_line_width = lambda: width_dpi

    def process_type_for_coverage_track(self):
        default_plot_type = 'fill'
        self.plot_type = default_plot_type
        self.size = None

        if self.properties['type'].find(":") > 0:
            self.plot_type, size = self.properties['type'].split(":")
            try:
                self.size = float(size)
            except ValueError:
                self.log.warning("Invalid value: 'type = "
                                 f"{self.properties['type']}' in section:"
                                 f" {self.properties['section_name']}\n"
                                 "A number was expected after ':' and found "
                                 f"'{size}'. Will use default.\n")
        else:
            self.plot_type = self.properties['type']

        if self.plot_type not in ['line', 'points', 'fill']:
            self.log.warning(f"Invalid: 'type = {self.properties['type']}' in"
                             f" section: {self.properties['section_name']}\n"
                             "Will use default.\n")
            self.plot_type = default_plot_type

    def process_color(self, param, colormap_possible=False,
                      bed_rgb_possible=False, colormap_only=False,
                      default_value_is_colormap=False):
        """
        Put a valid color/colormap in self.properties[param]
        Args:
            param: param to check/update the value
            colormap_possible: if the self.properties[param] can be a colormap
            bed_rgb_possible: if the self.properties[param] can be 'bed_rgb'
            colormap_only: if the self.properties[param] must be a colormap

        Returns:
            True if the self.properties[param] is a colormap
            False if the self.properties[param] is not a colormap

        """
        default_value = self.DEFAULTS_PROPERTIES[param]
        valid_color = None
        if bed_rgb_possible and self.properties[param] == 'bed_rgb':
            return False
        if mc.is_color_like(self.properties[param]):
            valid_color = self.properties[param]
        # It can be a tuple (for example (1, 0.88, 0.66666) would be a valid color):
        # Warning: (1, 0.88, 2./3) is not a valid color anymore
        elif self.properties[param][0] == '(':
            match = color_tuple.match(self.properties[param].replace(' ', ''))
            if match is not None:
                try:
                    custom_color = tuple([float(v) for v in match.groups()])
                except ValueError as e:
                    self.log.warning(f"*WARNING*: '{param}' for section"
                                     f" {self.properties['section_name']}"
                                     f" raised an error:\n{e}\n"
                                     f"{param} has "
                                     "been set to "
                                     f"{default_value}.\n")
                    valid_color = default_value
                else:
                    if mc.is_color_like(custom_color):
                        valid_color = custom_color
                    else:
                        self.log.warning(f"*WARNING*: '{param}' for section"
                                         f" {self.properties['section_name']}"
                                         " is not valid. "
                                         f"{param} has "
                                         "been set to "
                                         f"{default_value}.\n")
                        valid_color = default_value
            else:
                self.log.warning(f"*WARNING*: '{param}' for section"
                                 f" {self.properties['section_name']}"
                                 " is not well formatted (expected (r, g, b), "
                                 "with r,g,b values as float). "
                                 f"{param} has "
                                 "been set to "
                                 f"{default_value}.\n")
                valid_color = default_value

        if not colormap_possible:
            if valid_color is None:
                self.log.warning(f"*WARNING*: '{param}' for section"
                                 f" {self.properties['section_name']}"
                                 " is not valid. "
                                 f"{param} has "
                                 "been set to "
                                 f"{default_value}.\n")
                valid_color = default_value
            self.properties[param] = valid_color
            return False
        else:
            valid_colormap = None
            message = ""
            # We will try to process the color as a colormap
            if valid_color is None:
                # If someone what to use its own colormap,
                # he can specify the rgb values or color values:
                # For example:
                # colormap = ['white', (1, 0.88, 0.66), (1, 0.74, 0.25), (1, 0.5, 0), (1, 0.19, 0), (0.74, 0, 0), (0.35, 0, 0)]
                # Warning:
                # colormap = ['white', (1, 0.88, 2./3), (1, 0.74, 0.25), (1, 0.5, 0), (1, 0.19, 0), (0.74, 0, 0), (0.35, 0, 0)]
                # is not any more a valid color because of 2./3
                if self.properties[param][0] == '[':
                    if self.properties[param][-1] == ']':
                        # We remove all space and quote
                        prepared_color_list = re.sub(" |\'|\"", "", self.properties[param][1:-1])
                        # We extract individual colors
                        match = block_no_comma_outside_parenthesis.findall(prepared_color_list)
                        if match is not None:
                            # We check the color which start with '(' are (r,g,b) with rgb as floats
                            if all([color_tuple.match(v) is not None
                                    for v in match if v[0] == '(']):
                                # We try to convert them as float:
                                try:
                                    custom_colors = [tuple([float(v) for v in color_tuple.match(v).groups()])
                                                     if v[0] == '(' else v for v in match]
                                except ValueError:
                                    message = "some (r,g,b) values of the list could not be converted to float"
                                else:
                                    try:
                                        valid_colormap = mc.LinearSegmentedColormap.from_list(
                                            'custom', custom_colors, N=100)
                                    except ValueError:
                                        message = "the list of color could not be converted to colormap"
                            else:
                                message = "there is no color between brackets"
                        else:
                            message = "some colors starting with ( in the color" \
                                      " list are not formatted (r,g,b) with r,g,b as float"
                    if message != "":
                        message = f" ({message})"
                else:
                    if self.properties[param] in dir(plt.cm):
                        valid_colormap = self.properties[param]
        # Here, colormap is possible
        # valid_color is None or a valid color or the default value
        # valid_colormap is None or a valid colormap
        if valid_color is None and valid_colormap is None:
            self.log.warning(f"*WARNING* {param}: '{self.properties[param]}'"
                             f" for section {self.properties['section_name']}"
                             f" is not valid{message}. It has "
                             "been set to "
                             f"{default_value}.\n")
            self.properties[param] = default_value
            return default_value_is_colormap
        if colormap_only:
            if valid_colormap is None:
                # valid_color is not None
                self.log.warning(f"*WARNING* {param}: "
                                 f"'{self.properties[param]}' for section"
                                 f" {self.properties['section_name']}"
                                 f" is not valid{message}. It has "
                                 "been set to "
                                 f"{default_value}.\n")
                valid_colormap = default_value
            self.properties[param] = valid_colormap
            return True
        else:
            if valid_color is not None:
                self.properties[param] = valid_color
                return False
            else:
                self.properties[param] = valid_colormap
                return True

    def checkoperation(self):
        "Will check if the operation is 'safe'"
        allowed_words = ['second_file', 'file',
                         'sum', 'min', 'max',
                         'log1p', 'log']
        allowed_signs = ['+', '-', '*', '/',
                         '(', ')', '.', ',', ' '] + \
                        [f"{i}" for i in range(10)]
        operation = self.properties['operation']
        for word in allowed_words:
            operation = operation.replace(word, "")
        forbidden_signs = [s for s in operation if s not in allowed_signs]
        if len(forbidden_signs) > 0:
            raise InputError(f"operation: {self.properties['operation']}"
                             " uses signs which are not allowed: "
                             f"{','.join(forbidden_signs)}.")

    @staticmethod
    def check_chrom_str_bytes(iteratable_obj, p_obj):
        # determine type
        if isinstance(p_obj, list) and len(p_obj) > 0:
            type_ = type(p_obj[0])
        else:
            type_ = type(p_obj)
        if not isinstance(type(next(iter(iteratable_obj))), type_):
            if type(next(iter(iteratable_obj))) is str:
                p_obj = to_string(p_obj)
            elif type(next(iter(iteratable_obj))) in [bytes, np.bytes_]:
                p_obj = to_bytes(p_obj)
        return p_obj

    def plot_custom_cobar(self, axis, fraction=0.95):
        if self.properties.get('transform', 'no') in ['log', 'log1p']:
            # get a useful log scale
            # that looks like [1, 2, 5, 10, 20, 50, 100, ... etc]

            formatter = LogFormatter(10, labelOnlyBase=False)
            aa = np.array([1, 2, 5])
            tick_values = np.concatenate([aa * 10 ** x for x in range(10)])
            try:
                cobar = plt.colorbar(self.img, ticks=tick_values,
                                     format=formatter, ax=axis,
                                     fraction=fraction)
            except AttributeError:
                return
        else:
            try:
                cobar = plt.colorbar(self.img, ax=axis, fraction=fraction)
            except AttributeError:
                try:
                    cobar = plt.colorbar(self.colormap, ax=axis, fraction=fraction)
                except AttributeError:
                    return

        cobar.solids.set_edgecolor("face")
        cobar.ax.tick_params(labelsize='smaller')
        cobar.ax.yaxis.set_ticks_position('left')
        # adjust the labels of the colorbar
        # Get ticks positions
        ticks = cobar.ax.get_yticks()
        # Fix them
        cobar.set_ticks(ticks)
        # Set the corresponding labels
        labels = cobar.ax.set_yticklabels(ticks.astype('float32'))
        (vmin, vmax) = cobar.mappable.get_clim()
        for idx in np.where(ticks == vmin)[0]:
            # if the label is at the start of the colobar
            # move it above avoid being cut or overlapping with other track
            labels[idx].set_verticalalignment('bottom')
        for idx in np.where(ticks == vmax)[0]:
            # if the label is at the end of the colobar
            # move it a bit inside to avoid overlapping
            # with other labels
            labels[idx].set_verticalalignment('top')

    def adjust_ylim(self, axis):
        ymax = self.properties.get('max_value', None)
        ymin = self.properties.get('min_value', None)
        plot_ymin, plot_ymax = axis.get_ylim()
        if ymax is None:
            ymax = plot_ymax
        else:
            ymax = transform(np.array([ymax]), self.properties.get('transform', 'no'),
                             self.properties.get('log_pseudocount', 0),
                             'ymax')[0]
        if ymin is None:
            ymin = plot_ymin
        else:
            ymin = transform(np.array([ymin]), self.properties.get('transform', 'no'),
                             self.properties.get('log_pseudocount', 0),
                             'ymin')[0]

        if self.properties.get('orientation', None) == 'inverted':
            axis.set_ylim(ymax, ymin)
        else:
            axis.set_ylim(ymin, ymax)

    def __del__(self):
        return
