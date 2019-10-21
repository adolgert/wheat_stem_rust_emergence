import Queue
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler


counties=[1003, 1053, 1067, 1093, 5001, 5017, 5031, 5033, 5035, 5041, 5075, 5077, 5079, 5081, 5089, 5093, 5095, 5111, 5117, 5143, 6049, 6093, 6097, 8069, 8077, 12039, 13087, 13195, 13231, 13261, 13269, 13277, 16011, 16021, 16027, 16057, 16061, 17019, 17045, 17055, 17059, 17065, 17077, 17095, 17121, 17139, 17145, 17157, 17163, 17177, 17189, 17193, 17201, 18017, 18023, 18027, 18033, 18047, 18051, 18083, 18121, 18129, 18153, 18157, 18159, 18179, 19033, 19069, 19149, 19167, 20001, 20023, 20027, 20033, 20035, 20039, 20041, 20051, 20053, 20055, 20057, 20061, 20065, 20077, 20079, 20089, 20099, 20103, 20109, 20113, 20115, 20123, 20125, 20133, 20137, 20143, 20147, 20151, 20153, 20155, 20157, 20159, 20161, 20167, 20169, 20175, 20179, 20181, 20183, 20185, 20191, 20193, 20201, 20207, 20209, 21075, 21225, 22001, 22009, 22015, 22033, 22041, 22045, 22055, 22079, 22083, 22107, 22121, 22125, 26011, 26015, 26049, 26065, 26099, 26105, 26155, 27005, 27011, 27015, 27019, 27027, 27037, 27039, 27045, 27047, 27049, 27051, 27055, 27061, 27069, 27083, 27087, 27089, 27093, 27099, 27103, 27107, 27109, 27111, 27113, 27119, 27121, 27123, 27125, 27127, 27129, 27135, 27137, 27139, 27143, 27145, 27149, 27151, 27153, 27155, 27157, 27159, 27161, 27163, 27167, 27169, 28049, 28081, 28083, 28097, 28125, 28151, 29019, 29083, 29101, 29103, 29133, 29139, 29143, 29217, 30019, 30031, 30073, 30083, 30111, 31001, 31033, 31035, 31057, 31059, 31063, 31087, 31101, 31109, 31111, 31129, 31145, 31155, 31157, 31159, 31169, 31185, 36109, 37155, 38001, 38003, 38007, 38009, 38013, 38015, 38017, 38019, 38021, 38023, 38027, 38029, 38031, 38035, 38039, 38041, 38045, 38047, 38049, 38051, 38055, 38057, 38061, 38063, 38067, 38069, 38071, 38073, 38075, 38077, 38079, 38081, 38083, 38091, 38093, 38095, 38097, 38099, 38101, 38103, 38105, 39129, 39173, 40015, 40031, 40033, 40039, 40043, 40047, 40053, 40055, 40059, 40065, 40075, 40093, 40119, 40141, 40149, 40153, 41003, 41045, 41049, 41059, 41061, 41063, 41065, 45011, 46003, 46005, 46011, 46013, 46021, 46025, 46029, 46031, 46037, 46045, 46049, 46051, 46059, 46065, 46067, 46069, 46075, 46077, 46083, 46087, 46091, 46097, 46099, 46103, 46107, 46109, 46111, 46115, 46119, 46123, 46125, 46127, 46129, 46135, 47131, 48013, 48025, 48027, 48041, 48049, 48059, 48083, 48085, 48095, 48099, 48113, 48121, 48139, 48181, 48209, 48249, 48253, 48275, 48287, 48297, 48307, 48309, 48325, 48331, 48333, 48381, 48399, 48401, 48411, 48463, 48469, 48481, 48485, 48487, 48491, 48493, 48503, 49003, 51121, 51159, 53001, 53013, 53057, 53071, 53075, 54025, 54063, 54089, 55009, 55013, 55015, 55021, 55025, 55027, 55029, 55039, 55045, 55047, 55055, 55059, 55071, 55087, 55089, 55101, 55105, 55111, 55117, 55127, 55131, 55133, 55139]

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

def next_county():
    global county_queue
    if not county_queue.empty():
        geoid=county_queue.get()
        print geoid
        return geoid
    else:
        return 0

def count():
    global county_queue
    return county_queue.qsize()


def serve():
    global county_queue
    county_queue=Queue.Queue()
    for c in counties:
        county_queue.put(c)

    # Create server
    server = SimpleXMLRPCServer(("128.84.31.84", 8000),
                                requestHandler=RequestHandler)
    server.register_introspection_functions()
    
    # Register pow() function; this will use the value of
    # pow.__name__ as the name, which is just 'pow'.
    server.register_function(next_county)
    server.register_function(count)
    
    # Run the server's main loop
    server.serve_forever()

if __name__ == '__main__':
    serve()