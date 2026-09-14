// SPDX-License-Identifier: LGPL-2.1-or-later

/******************************************************************************
 *   Copyright (c) 2012 Jan Rheinländer <jrheinlaender@users.sourceforge.net> *
 *                                                                            *
 *   This file is part of the FreeCAD CAx development system.                 *
 *                                                                            *
 *   This library is free software; you can redistribute it and/or            *
 *   modify it under the terms of the GNU Library General Public              *
 *   License as published by the Free Software Foundation; either             *
 *   version 2 of the License, or (at your option) any later version.         *
 *                                                                            *
 *   This library  is distributed in the hope that it will be useful,         *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of           *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            *
 *   GNU Library General Public License for more details.                     *
 *                                                                            *
 *   You should have received a copy of the GNU Library General Public        *
 *   License along with this library; see the file COPYING.LIB. If not,       *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,            *
 *   Suite 330, Boston, MA  02111-1307, USA                                   *
 *                                                                            *
 ******************************************************************************/

#pragma once

#include "TaskTransformedParameters.h"
#include "ViewProviderTransformed.h"
#include <Mod/PartDesign/App/FeatureLinearPattern.h>

class QCheckBox;
class QTimer;
class Ui_TaskPatternParameters;

namespace PartGui
{
class PatternParametersWidget;
class PickField;
}

namespace PartDesignGui
{

class TaskMultiTransformParameters;

class TaskPatternParameters: public TaskTransformedParameters
{
    Q_OBJECT

public:
    /// Which field the next click in the 3D view goes to
    enum class PickTarget
    {
        None,
        Features,
        Direction1,  ///< the axis, for a polar pattern
        Direction2
    };

    /// The next standalone pattern panel opens with its Features field active; the
    /// "click the feature to copy" start uses it so further clicks add more features
    static void startWithFeaturesPicking();

    /// The one place a pick field is turned on or off
    void setPickTarget(PickTarget next);
    PickTarget pickTarget() const
    {
        return target;
    }

Q_SIGNALS:
    void pickTargetChanged();

public:
    /// Constructor for task with ViewProvider
    explicit TaskPatternParameters(ViewProviderTransformed* TransformedView, QWidget* parent = nullptr);
    /// Constructor for task with parent task (MultiTransform mode)
    TaskPatternParameters(TaskMultiTransformParameters* parentTask, QWidget* parameterWidget);
    ~TaskPatternParameters() override;

    void apply() override;

protected:
    void onSelectionChanged(const Gui::SelectionChanges& msg) override;
    bool eventFilter(QObject* watched, QEvent* event) override;

private Q_SLOTS:
    void onUpdateViewTimer();
    // Slot to handle reference selection request from the widget
    void onParameterWidgetRequestReferenceSelection();
    void onParameterWidgetRequestReferenceSelection2();
    // Slot to handle parameter changes from the widget
    void onParameterWidgetParametersChanged();
    // Update view signal (might be redundant now)
    void onUpdateView(bool on) override;


private:
    void setupParameterUI(QWidget* widget) override;
    void retranslateParameterUI(QWidget* widget) override;

    void updateUI();
    void kickUpdateViewTimer() const;
    void updateSpacingLabels();

    void bindProperties();

    // Task-specific logic remains
    void showOriginAxes(bool show);
    /// Gives a newly picked second direction the same kind of start as the first
    void startSecondDirection(PartDesign::LinearPattern* pattern);

    void setupFeaturesAndOptions();
    void updateFeaturesField();
    void toggleFeature(const Gui::SelectionChanges& msg);
    void showPickHints();

    Base::Vector3d getStartPoint() const;

    PartGui::PatternParametersWidget* parametersWidget = nullptr;
    PartGui::PatternParametersWidget* parametersWidget2 = nullptr;

    PartGui::PickField* featuresField = nullptr;
    QCheckBox* wholeBodyCheck = nullptr;
    QCheckBox* updateViewCheck = nullptr;
    PickTarget target = PickTarget::None;
    static bool featuresPickingRequested;

    std::unique_ptr<Ui_TaskPatternParameters> ui;
    QTimer* updateViewTimer = nullptr;
};


/// simulation dialog for the TaskView
class TaskDlgLinearPatternParameters: public TaskDlgTransformedParameters
{
    Q_OBJECT

public:
    explicit TaskDlgLinearPatternParameters(ViewProviderTransformed* LinearPatternView);
};

}  // namespace PartDesignGui
