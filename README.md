# Dynamic Layers QGIS Plugin

## Description

This plugin helps to change the datasources of many layers at once, for example to create different versions of the same project on different extents.

You can use some variables such as {$myvar} inside the layer datasource template, and then define theses variables (from a table or from an input vector source).

Finally you apply the variables values on every configured layer via the apply button, and you can see the changes before saving the project.

## Installation

You can install the plugin from QGIS extension manager. At present, it has the status "experimental".

## Usage

At first, you must set up a QGIS project with some layers. This project will serve as a basis to create derived child projects. Once you have a project, you can open the plugin main dialog : Menu Extension / Dynamic Layers

### Configure layers

#### Layers

The project layers are listed in the table, which the following properties

* **id** : Internal QGIS layer id ( stored in project *.qgs file )
* **name** : The layer name ( as defined in QGIS legend )
* **dynamicDatasourceActive** : True means the layer is activated : the dynamic datasource content set in the bottom text box will be used when applying variables on the project.

The activated layers have a green background. You can sort the layers in the table by clicking on one of the header columns.

#### Dynamic properties

This interface allows you to activate dynamic datasource for the selected layers ( the layer highlighted in the table above ).

You can copy the current datasource from the layer definition by clicking on the **Copy from current datasource** button.

Then you can change the datasource, and use variables, with the syntax **{$varname}** by changing "varname" by any name you want ( but you need to use only letters and digits, no spaces or punctuation chars ).

For example, if the original layer datasource for a Shapefile is

```
/tmp/town_france.shp
```

You can use a "country" variable

```
/tmp/town_{$country}.shp
```
You can use as many variables as needed, and for any type of datasource. For example, you could change a username or table definition of a PostGIS layer, or a WHERE clause, like this

```
service='myservice' sslmode=disable key='gid' table="(
SELECT row_number() OVER () AS gid, *
FROM mytable
WHERE year = {$year}
)" sql=
```

### Configure project

This tab allows you to define 2 differents things:

* Some project OWS Server properties, used only if you publish your project with QGIS Server:  **Project title** (The title of the map ) and **Project description** ( the map description ). You can also use variables in these parameters, such as the following example for the title

```
Map of the towns of {$country} (year : {$year} )
```

You can use the button **Copy properties from project** to get the title and description wich are set in the project properties tab of QGIS ( Menu Project / Project properties )

* An **extent layer** and **extent margin**. When applying the variables on the project, the plugin will zoom to the extent of the selected layer, plus the given margin.


### Set variables

#### Set variables manually

You can add or remove variables in the table by using the form at the bottom.
You can also modify the variable value by entering a new value in corresponding the table cell.

Once you have added your variables and added a value for each one, you can **apply variables on project** by clicking on the correspondong button.

This will replace each activated layer datasource by the dynamic datasource modified via the variables, and then zoom to the extent layer.

You can now save the project as another project, or simply save the current project. All the configuration is stored in the QGIS project, so you can reuse it in the future.

#### Set variables from a vector layer

You can use a project vector layer as an input for variables. In this case, each chosen layer field will be used as variable name.

You must then use a QGIS expression to filter one line of the source layer (if more than one line is returned by the expression filter, the first feature will be used ).

For example, if your source layer has this attribute table

id |  year | country
------------- | ------------- | ---
1  |  2013 | Spain
2  | 2012 | France
3  |  2012 | Japan
4  | 2015 | Canada

And if you use the expresion

```
id = 3
```
You will have the following variables and values

variable |  value
------------- | -------------
id  |  3
year  | 2012
country  |  Japan


Once source layer and expression are set, you can apply the found variables on your project by clicking on the button **Apply on project**



### Log

This tab will show the plugin log messages.

## Demo

Video tutorials:

* plugin presentation : https://vimeo.com/141541813
* use a vector layer as a variable data source : https://vimeo.com/141546964


## Server side plugin

### Server plugin Installation

#### Prerequisites

We assume that you are working on a fresh install with Apache and FCGI module installed with:

```bash
$ sudo apt-get install apache2 libapache2-mod-fcgid
$ # Enable FCGI daemon apache module
$ sudo a2enmod fcgid
```

#### Install QGIS Server

See : http://qgis.org/fr/site/forusers/download.html

To install QGIS Server, after having added the official QGIS package repository and added the public key, you can just do

```bash
$ sudo apt-get install qgis-server python-qgis
```

#### Install Dynamic plugin


```bash
$ sudo mkdir -p /opt/qgis-server/plugins
$ cd /opt/qgis-server/plugins
$ sudo wget https://github.com/3liz/QgisDynamicLayersPlugin/archive/master.zip
$ # In case unzip was not installed before:
$ sudo apt-get install unzip
$ sudo unzip master.zip 
$ sudo mv QgisDynamicLayersPlugin-master QgisDynamicLayersPlugin
```

#### Apache virtual host configuration

You can create a dedicated Apache virtual host for QGIS Server, or modify an existing host by adding some environment variables.

Here is an example of a dedicated virtual host configuration
The virtual host configuration, stored in /etc/apache2/sites-available/001-qgis-server.conf:

```
    <VirtualHost *:80>
        ServerAdmin webmaster@localhost
        DocumentRoot /var/www/html
     
        ErrorLog ${APACHE_LOG_DIR}/qgis-server-error.log
        CustomLog ${APACHE_LOG_DIR}/qgis-server-access.log combined
     
        # Longer timeout for WPS... default = 40
        FcgidIOTimeout 120 
        FcgidInitialEnv LC_ALL "en_US.UTF-8"
        FcgidInitialEnv PYTHONIOENCODING UTF-8
        FcgidInitialEnv LANG "en_US.UTF-8"
        FcgidInitialEnv QGIS_DEBUG 1
        FcgidInitialEnv QGIS_SERVER_LOG_FILE /tmp/qgis-000.log
        FcgidInitialEnv QGIS_SERVER_LOG_LEVEL 0
        FcgidInitialEnv QGIS_PLUGINPATH "/opt/qgis-server/plugins"
     
        # ABP: needed for QGIS HelloServer plugin HTTP BASIC auth
        <IfModule mod_fcgid.c>
            RewriteEngine on
            RewriteCond %{HTTP:Authorization} .
            RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
        </IfModule>
     
        ScriptAlias /cgi-bin/ /usr/lib/cgi-bin/
        <Directory "/usr/lib/cgi-bin">
            AllowOverride All
            Options +ExecCGI -MultiViews +FollowSymLinks
            Require all granted
            #Allow from all
      </Directory>
    </VirtualHost>
```

Enable the virtual host and restart Apache:

```bash
$ sudo a2ensite 001-qgis-server
$ sudo service apache2 restart
```

#### Grant write acccess to the folder containing the parent project

You need to give write permission to the apache user (for example www-data ) in order to enable the server plugin to write a new project in it. Make sure the folder has got the right permissions.

Now you must be able to use the plugin server side !


### Usage

This plugin contains a filter for QGIS Server, which allows to create a child project based on a "parent" project configured with Dynamic layers. Once instaled on server, you can use a new request with the following parameters

* **SERVICE** : dynamiclayers  (must be spelled corectly )
* **MAP** : the full path to the parent project. For example  "/tmp/someproject.qgs"
* **DLSOURCELAYER** : the name of the source layer defined in the **Set variables from a vector layer**. For example "variable_source"
* **DLEXPRESSION** : a QGIS expression to select the feature from the source layer wich contains the needed data for the child project to be generated. For example : "id = 3"

Of course, the expression must be url-encoded. Here is an request URL example

```
http://localhost/cgi-bin/qgis_mapserv.fcgi?MAP=/tmp/someproject.qgs&SERVICE=dynamiclayers&DLSOURCELAYER=variable_source&DLEXPRESSION=%22id%22%3D3
```

This request will ask the DynamicLayers Server plugin to create a child project based on the source project "variable_source" ( configured via the desktop QGIS plugin ), and will send back a JSON response containing the name of the created project.

For example:

```
{
	"status": 1, 
	"childProject": "someproject__variable_source_idIN3.qgs", 
	"message": "Child project has been updated"
}
```

If the child project has already been created before, the plugin will **not** recreate it, but return the following response

```
{
	"status": 1, 
	"childProject": "someproject__variable_source_idIN3.qgs", 
	"message": "Child project is already up-to-date"
}
```

But if you have modified the parent project in the meantime, the plugin will detect that the parent project has been changed, and will recreate the child project.


### Use with Lizmap Web Client

**Lizmap Web Client V3** (currently the master branch ) has the capabilities to use a parent project and to generate a new map based on the plugin **DynamicLayers.**

#### Installation

Of course, the QGIS plugin DynamicLayers must been installed, as described above.

You must then  install the Lizmap module **dynamicLayers**. This module is shiped with Lizmap Web Client 3 and above, but is not installed by default.

To do so, you must add the following line in the section **[modules]** of lizmap local configuration file. In the following example, we assume that Lizmap Web Client is already installed and working, and the root of Lizmap installation is /var/www/lizmap-web-client/

```
cd /var/www/lizmap-web-client/
nano lizmap/var/config/localconfig.ini.php
```
In this file, you should see a section [modules], if not create it, and activate the module dynamicLayers by writing its access level as follow:

```
[modules]

dynamicLayers.access = 2
```

Then save the file. Now you can install the module via

```
sudo lizmap/install/set_rights.sh www-data www-data
php lizmap/install/installer.php
```

#### Usage

If you have a Lizmap map corresponding to this URL

```
http://lizmap.localhost/index.php/view/map/?repository=somerepo&project=someproject
```

You can for example configure the QGIS project **someproject.qgs** with the plugin Dynamic Layers, and then pass some parameters in a dedicated URL to let the combo Lizmap / DynamicLayers **create a derivated map based on the initial map**. For example, use the following URL:

```
http://lizmap.localhost/index.php/dynamicLayers/map/?repository=somerepo&project=someproject&dlsourcelayer=variable_source&dlexpression=%22id%22%3D3
```

Basically, this URL is the same as the normal Lizmap one, but:

* we have replaced **view/map/** by **dynamicLayers/map/**
* we have added the 2 parameters **dlsourcelayer** and **dlexpression** (in lower case) containing the same values as shown previously.

Lizmap will then:

* Use the DynamicLayers server plugin to **create a child project**
* Copy and adapt the **Lizmap configuration** of the parent project for the child project ( global and layers extent, etc.)
* **Redirect to the new map**, for example to 

```
http://lizmap.localhost/index.php/view/map/?repository=somerepo&project=someproject__variable_source_idIN3
```

This way you can spend time creating a beautiful map for you parent project, publish it via Lizmap, and then automatically publish many child projects as derivated map, with no effort !

## Authors

Michaël DOUCHIN ( 3liz.com ) - @mdouchin


## Contributors

Originally funded by Dyopta, France http://www.dyopta.com/

## Licence

GPL V2
