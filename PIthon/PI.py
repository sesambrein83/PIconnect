""" PI
    Core containers for connections to PI databases
"""
from PIthon.AFSDK import AF
from PIData import PISeries, PISeriesContainer
from PIthon._operators import add_operators, operators


class PIServer(object):
    """Context manager for connections to a PI server."""
    version = '0.2.1'

    servers = {server.Name: server for server in AF.PI.PIServers()}
    default_server = AF.PI.PIServers().DefaultPIServer

    def __init__(self, server=None):
        self.connection = self.servers.get(server, self.default_server)

    def __enter__(self):
        force_connection = False  # Don't force to retry connecting if previous attempt failed
        self.connection.Connect(force_connection)
        return self

    def __exit__(self, *args):
        self.connection.Disconnect()

    def __repr__(self):
        return u'%s(\\\\%s)' % (self.__class__.__name__, self.server_name)

    @property
    def server_name(self):
        """Return the name of the connected PI server as a string."""
        return self.connection.Name

    def search(self, query, source=None):
        """Search for tags on the connected PI server

           PI Points are matched to *query*, which can be provided as a string or
           a list of strings. In either case a single, unnested, list of
           Pithon.PI.PIPoints is returned.
        """
        if isinstance(query, list):
            return [y for x in query for y in self.search(x, source)]
        elif not isinstance(query, basestring):
            raise TypeError('Argument query must be either a string or a list of strings,' +
                            'got type ' + str(type(query)))
        return [PIPoint(pi_point) for pi_point in
                AF.PI.PIPoint.FindPIPoints(self.connection, query, source, None)]


@add_operators(
    operators=operators,
    members=[
        '_current_value',
        'interpolated_values'
    ],
    newclassname='VirtualPIPoint',
    attributes=['pi_point']
)
class PIPoint(PISeriesContainer):
    """Reference to a PI Point to get data and corresponding metadata from the server.

        TODO: Build a PI datacontainer from which PIPoint and PIAFAttribute subclass.
    """
    version = '0.3.0'

    def __init__(self, pi_point):
        self.pi_point = pi_point
        self.tag = pi_point.Name
        self.__attributes_loaded = False
        self.__raw_attributes = {}

    def __repr__(self):
        return u'%s(%s, %s; Current Value: %s %s)' % (self.__class__.__name__,
                                                      self.tag,
                                                      self.description,
                                                      self.current_value,
                                                      self.units_of_measurement)

    @property
    def current_value(self):
        """Return the last recorded value for this PI Point."""
        return self._current_value()

    @property
    def last_update(self):
        """Return the time at which the last value for this PI Point was recorded."""
        return PISeries.timestamp_to_index(self.pi_point.CurrentValue().Timestamp.UtcTime)

    @property
    def raw_attributes(self):
        """Return a dictionary of the raw attributes of the PI Point."""
        self.__load_attributes()
        return self.__raw_attributes

    @property
    def units_of_measurement(self):
        """Return the units of measument in which values for this PI Point are reported."""
        self.__load_attributes()
        return self.__raw_attributes['engunits']

    @property
    def description(self):
        """Return the description of the PI Point.

        TODO: Add setter to alter displayed description
        """
        self.__load_attributes()
        return self.__raw_attributes['descriptor']

    def __load_attributes(self):
        """Load the raw attributes of the PI Point from the server"""
        if not self.__attributes_loaded:
            self.pi_point.LoadAttributes([])
            self.__attributes_loaded = True
        self.__raw_attributes = {att.Key: att.Value for att in self.pi_point.GetAttributes([])}

    @property
    def name(self):
        return self.tag

    def _current_value(self):
        """Return the last recorded value for this PI Point (internal use only)."""
        return self.pi_point.CurrentValue().Value

    def _recorded_values(self, time_range, boundary_type, filter_expression):
        include_filtered_values = False
        return self.pi_point.RecordedValues(time_range,
                                            boundary_type,
                                            filter_expression,
                                            include_filtered_values)

    def _interpolated_values(self, time_range, interval, filter_expression):
        """Internal function to actually query the pi point"""
        include_filtered_values = False
        return self.pi_point.InterpolatedValues(time_range,
                                                interval,
                                                filter_expression,
                                                include_filtered_values)

    def _normalize_filter_expression(self, filter_expression):
        return filter_expression.replace('%tag%', self.tag)
