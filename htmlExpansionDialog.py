# -*- coding: utf-8 -*-
"""
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QVariant, Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QIcon

from qgis.core import Qgis, QgsVectorLayer, QgsFields, QgsField, QgsWkbTypes, QgsMapLayerProxyModel, QgsProject

from .htmlParser import HTMLExpansionProcess
# import traceback

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'htmlExpansion.ui'))
HTML_FIELDS_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'htmlFields.ui'))

def tr(string):
    return QCoreApplication.translate('Processing', string)

class HTMLExpansionDialog(QDialog, FORM_CLASS):
    def __init__(self, iface):
        """Initialize the HTML expansion dialog window."""
        super(HTMLExpansionDialog, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self.inputLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.inputLayerComboBox.layerChanged.connect(self.layerChanged)
        self.typeComboBox.addItems([
            tr('Expand from a 2 column HTML table'),
            tr('Expand from "tag = value" pairs'),
            tr('Expand from "tag: value" pairs')])

    def showEvent(self, event):
        """The dialog is being shown. We need to initialize it."""
        super(HTMLExpansionDialog, self).showEvent(event)
        self.layerChanged()

    def accept(self):
        """Called when the OK button has been pressed."""
        layer = self.inputLayerComboBox.currentLayer()
        if not layer:
            return
        newlayername = self.outputLayerLineEdit.text().strip()
        type = self.typeComboBox.currentIndex()

        # Find all the possible fields in the description area
        field = self.descriptionComboBox.currentField()
        index = layer.fields().indexFromName(field)
        if index == -1:
            self.iface.messageBar().pushMessage("", "Invalid field name", level=Qgis.Warning, duration=3)
            return

        # Set up the HTML expansion processor
        self.htmlProcessor = HTMLExpansionProcess(layer, field, type)
        self.htmlProcessor.addFeature.connect(self.addFeature)
        # Have it generate a list of all possible expansion field names
        self.htmlProcessor.autoGenerateFileds()

        # From the expansion processor get the list of possible expansion fields
        # and show a popup of them so the user can select which he wants in the output.
        fieldsDialog = HTMLFieldSelectionDialog(self.iface, self.htmlProcessor.fields())
        fieldsDialog.exec_()
        # From the users selections of expansion fields, set them in the processor.
        # This is just a list of names.
        self.htmlProcessor.setDesiredFields(fieldsDialog.selected)

        wkbtype = layer.wkbType()
        layercrs = layer.crs()
        # Create the new list of attribute names from the original data with the unique
        # expansion names.
        fieldsout = QgsFields(layer.fields())
        for item in self.htmlProcessor.uniqueDesiredNames(layer.fields().names()):
            fieldsout.append(QgsField(item, QVariant.String))
        newLayer = QgsVectorLayer("{}?crs={}".format(QgsWkbTypes.displayString(wkbtype), layercrs.authid()), newlayername, "memory")

        self.dp = newLayer.dataProvider()
        self.dp.addAttributes(fieldsout)
        newLayer.updateFields()

        # Process each record in the input layer with the expanded entries.
        # The actual record is added with the 'addFeature' callback
        self.htmlProcessor.processSource()
        self.htmlProcessor.addFeature.disconnect(self.addFeature)

        newLayer.updateExtents()
        QgsProject.instance().addMapLayer(newLayer)
        self.close()

    def addFeature(self, f):
        self.dp.addFeatures([f])

    def layerChanged(self):
        if not self.isVisible():
            return
        layer = self.inputLayerComboBox.currentLayer()
        self.descriptionComboBox.setLayer(layer)
        if layer:
            self.descriptionComboBox.setField('description')

class HTMLFieldSelectionDialog(QDialog, HTML_FIELDS_CLASS):
    def __init__(self, iface, feat):
        super(HTMLFieldSelectionDialog, self).__init__(iface.mainWindow())
        self.setupUi(self)
        self.iface = iface
        self.feat = feat
        self.selected = []
        self.selectAllButton.clicked.connect(self.selectAll)
        self.clearButton.clicked.connect(self.clearAll)
        self.checkBox.stateChanged.connect(self.initModel)
        self.initModel()

    def initModel(self):
        self.model = QStandardItemModel(self.listView)
        state = self.checkBox.isChecked()
        for key in list(self.feat.keys()):
            if state is False or self.feat[key] > 0:
                item = QStandardItem()
                item.setText(key)
                item.setCheckable(True)
                item.setSelectable(False)
                self.model.appendRow(item)
        self.listView.setModel(self.model)
        self.listView.show()

    def selectAll(self):
        cnt = self.model.rowCount()
        for i in range(0, cnt):
            item = self.model.item(i)
            item.setCheckState(Qt.Checked)

    def clearAll(self):
        cnt = self.model.rowCount()
        for i in range(0, cnt):
            item = self.model.item(i)
            item.setCheckState(Qt.Unchecked)

    def accept(self):
        self.selected = []
        cnt = self.model.rowCount()
        for i in range(0, cnt):
            item = self.model.item(i)
            if item.checkState() == Qt.Checked:
                self.selected.append(item.text())
        self.close()
