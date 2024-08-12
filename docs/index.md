---
hide:
  - navigation
  - toc
---

# DynamicLayers

## Description

This plugin helps to change the datasource's of many layers at once, for example to create different versions of the
same project on different extents.

You can use some variables such as `$myvar` inside the layer datasource template, and then define these variables
(from a table or from an input vector source).

Finally, you can apply the variables values on every configured layer via the **apply** button, and you can see the
changes before saving the project.

## Installation

For now, the plugin is not published on QGIS.org.
You need to download a ZIP either from a [stable release](https://github.com/3liz/QgisDynamicLayersPlugin/releases) or
from a [commit](https://github.com/3liz/QgisDynamicLayersPlugin/actions/workflows/ci.yml)

## Usage

At first, you must set up a QGIS project with some layers. This project will serve as a basis to create derived child projects.
Once you have a project, you can open the plugin main dialog.

### Configure layers

#### Layers

The project layers are listed in the table, which the following properties

* **ID** : Internal QGIS layer ID (stored in project `*.qgs` file)
* **Name** : The layer name
* **Dynamic Datasource Active** : True means the layer is activated : the dynamic datasource content set in the bottom
  text box will be used when applying variables on the project.

The activated layers have a green background. You can sort the layers in the table by clicking on one of the header columns.

#### Dynamic properties

This interface allows you to activate dynamic datasource for the selected layers (the layer highlighted in the table above).

You can copy the current datasource from the layer definition by clicking on the **Copy from current datasource** button.

Then you can change the datasource, and use variables, with the syntax `$varname` by changing `varname` by any name you
want (but you need to use only letters and digits, no spaces or punctuation chars).

Note, both syntax are valid : `$varname` or `${varname}` (which can become `language${languageCode}`).

For example, if the original layer datasource for a Shapefile is

```bash
/tmp/town_france.shp
```

You can use a "country" variable

```bash
/tmp/town_${country}.shp
```

You can use as many variables as needed, and for any type of datasource. For example, you could change a username or
table definition of a PostGIS layer, or a `WHERE` clause, like this :

```sql
service='myservice' sslmode=disable key='gid' table="(
SELECT row_number() OVER () AS gid, *
FROM mytable
WHERE year = ${year}
)" sql=
```

#### Use variables in QGIS layer properties

We have seen above that you can use variables to define a new layer datasource.

You can also use variables

* Inside the layers **title** and **abstract **.
  Open the vector layer properties dialog, and in the **QGIS Server** panel, you can use variables in the definition of
  the **title** and the **abstract** properties.
* In the **vector layers field aliases**.
  In the vector properties dialog, tab *Fields*, you can use variables inside the aliases defined for each field.

**When applying variables with the plugin, all these properties will also be updated.** (See the "Set variables" chapter further on)

### Configure project

This tab allows you to define 2 different things:

* Some project with QGIS Server : **Project title** and **Project abstract**.
  You can also use variables in these parameters, such as the following example for the title

```
Map of the towns of $country (year : ${year} )
```

You can use the button **Copy properties from project** to get the title and description which are set in the project
properties tab of QGIS ( Menu Project / Project properties / QGIS Server )

* An **extent layer** and **extent margin**.
  When applying the variables on the project, the plugin will zoom to the extent of the selected layer,
  plus the given margin.


### Set variables

#### Set variables manually

You can add or remove variables in the table by using the form at the bottom.
You can also modify the variable value by entering a new value in corresponding the table cell.

Once you have added your variables and added a value for each one, you can **apply variables on project** by clicking
on the corresponding button.

This will replace each activated layer datasource by the dynamic datasource modified via the variables, and then zoom to
the extent layer.

You can now save the project as another project, or simply save the current project.
All the configuration is stored in the QGIS project, so you can reuse it in the future.

#### Set variables from a vector layer

You can use a vector layer as an input for variables. In this case, each chosen layer field will be used as variable name.

You must then use a QGIS expression to filter one line of the source layer.
If more than one line is returned by the expression filter, the first feature will be used.

For example, if your source layer has this attribute table

| id | year | country |
|----|------|---------|
| 1  | 2013 | Spain   |
| 2  | 2012 | France  |
| 3  | 2012 | Japan   |
| 4  | 2015 | Canada  |

And if you use the expression

```
id = 3
```
You will have the following variables and values

| variable | value |
|----------|-------|
| id       | 3     |
| year     | 2012  |
| country  | Japan |

Once source layer and expression are set, you can apply the found variables on your project by clicking on the button
**Apply on project**

### Log

This tab will show the plugin log messages.

### Processing

You can generate projects with a **coverage** layer :

1. You need make a first projects with all variables set in the previous plugin dialog.
2. Open the Processing algorithm, from the **Processing** menu.
3. Do not forget to read tooltips.

## Demo

Video tutorials:

* [Plugin presentation](https://vimeo.com/141541813)
* [Use a vector layer as a variable data source](https://vimeo.com/141546964)

## Contributors

Originally funded by Dyopta, France http://www.dyopta.com/
