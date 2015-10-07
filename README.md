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
------------- | ------------- | -- 
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


## Authors

Michaël DOUCHIN ( 3liz.com ) - @mdouchin


## Contributors

Originally funded by Dyopta, France http://www.dyopta.com/

## Licence

GPL V2
