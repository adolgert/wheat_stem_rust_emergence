#ifndef _CONFIG_HPP_
#define _CONFIG_HPP_ 1

#include <string>
#include <vector>
#include <map>
#include <iostream>
#include <fstream>
#include <sstream>
#include <boost/algorithm/string/split.hpp>
#include <boost/algorithm/string/trim.hpp>
#include <boost/algorithm/string/predicate.hpp>
#include <boost/algorithm/string/replace.hpp>

namespace land_use
{

    /*! Given a map from keys to values, add a new key and value
     *  but first see if any of the previous keys appear in the 
     *  new value. If so, replace them with the setting. The idea
     *  is that "myfile=%(basedir)/input.dat" can have "%(basedir)"
     *  replaced.
     */
    void add_keyval(std::map<std::string,std::string>& keyval,
                    std::vector<std::string>& line) {
        if (line.size()==2) {
            std::string val=line[1];

            for (auto key=keyval.cbegin(); key!=keyval.cend(); key++) {
                std::stringstream search_pattern;
                search_pattern << "%(" << key->first << ")s";
                boost::replace_all(val, search_pattern.str(), key->second);
            }

            keyval[line[0]]=val;
        } else {
            ;
        }
    }



    /*! Given a config file, append its contents to a key-value map. */
    bool read_config_file(const std::string& config_filename,
                          std::map<std::string,std::string>& keyval) {
        std::ifstream infile(config_filename);
        if (infile.is_open()) {
            std::string line;
            while (infile.good()) {
                getline( infile, line );
                boost::trim(line);
                if (!boost::istarts_with(line, "[") &&
                    !boost::istarts_with(line, "#")) {
                    std::vector<std::string> splitted;
                    boost::split(splitted, line, boost::is_any_of("="),
                                 boost::token_compress_on);
                    add_keyval(keyval, splitted);
                }
            }
        }
    }



    std::string config_get(const std::string& name) {
        std::map<std::string,std::string> keyval;
        std::vector<std::string> config_files;
        config_files.push_back("project.cfg");
        config_files.push_back("project_local.cfg");

        bool read_any=false;
        for (auto fname=config_files.begin(); fname!=config_files.end();
             fname++) {
            read_any=read_any || read_config_file(*fname, keyval);
        }
        if (keyval.find(name)!=keyval.end()) {
            return keyval[name];
        }
        return std::string();
    }

}



#endif // _CONFIG_HPP_
