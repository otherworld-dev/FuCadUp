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

#include <algorithm>
#include <cstring>

#include <QApplication>
#include <QCheckBox>
#include <QKeyEvent>
#include <QLabel>
#include <QMessageBox>
#include <QSignalBlocker>
#include <QTimer>
#include <QToolButton>
#include <QVBoxLayout>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>
#include <gp_Ax2.hxx>
#include <gp_Dir.hxx>
#include <gp_Vec.hxx>
#include <gp_Pnt.hxx>
#include <Standard_Failure.hxx>

#include <BRep_Builder.hxx>
#include <TopoDS_Compound.hxx>

#include <Inventor/SbVec3f.h>

#include <App/Document.h>
#include <App/DocumentObject.h>
#include <App/Origin.h>
#include <Base/Console.h>
#include <Base/Converter.h>
#include <Gui/Application.h>
#include <Gui/MainWindow.h>
#include <Gui/BitmapFactory.h>
#include <Gui/InputHint.h>
#include <Gui/Inventor/Draggers/Gizmo.h>
#include <Gui/Inventor/Draggers/SoLinearDragger.h>
#include <Gui/Inventor/Draggers/SoRotationDragger.h>
#include <Gui/Selection/Selection.h>
#include <Gui/Command.h>
#include <Gui/SpinBox.h>
#include <Gui/Utilities.h>
#include <Gui/View3DInventor.h>
#include <Gui/View3DInventorViewer.h>
#include <Gui/ViewProviderCoordinateSystem.h>
#include <Mod/PartDesign/App/Body.h>
#include <Mod/PartDesign/App/DatumLine.h>
#include <Mod/PartDesign/App/DatumPlane.h>
#include <Mod/PartDesign/App/FeatureLinearPattern.h>
#include <Mod/PartDesign/App/FeaturePolarPattern.h>
#include <Mod/PartDesign/App/FeatureAddSub.h>
#include <Mod/Part/Gui/PatternParametersWidget.h>
#include <Mod/Part/Gui/PickField.h>
#include <Mod/Part/App/Tools.h>

#include "ui_TaskPatternParameters.h"
#include "TaskPatternParameters.h"
#include "PatternDefaults.h"
#include "PatternFeaturePicker.h"
#include "ReferenceSelection.h"
#include "TaskMultiTransformParameters.h"


using namespace PartDesignGui;
using namespace Gui;

/* TRANSLATOR PartDesignGui::TaskPatternParameters */

bool TaskPatternParameters::featuresPickingRequested = false;

void TaskPatternParameters::startWithFeaturesPicking()
{
    featuresPickingRequested = true;
}

void TaskPatternParameters::cancelFeaturesPicking()
{
    featuresPickingRequested = false;
}

TaskPatternParameters::TaskPatternParameters(ViewProviderTransformed* TransformedView, QWidget* parent)
    : TaskTransformedParameters(TransformedView, parent)
    , ui(new Ui_TaskPatternParameters)
{
    setupUI();
    hideFeatureListControls();
    setupFeaturesAndOptions();
    setupGizmos();
    updateSpacingLabels();

    if (featuresPickingRequested) {
        featuresPickingRequested = false;
        // Once the dialog is up, so the hint row is not overwritten by the dialog's own
        QTimer::singleShot(0, this, [this]() { setPickTarget(PickTarget::Features); });
    }
}

TaskPatternParameters::TaskPatternParameters(
    TaskMultiTransformParameters* parentTask,
    QWidget* parameterWidget
)
    : TaskTransformedParameters(parentTask)
    , ui(new Ui::TaskPatternParameters)
{
    setupParameterUI(parameterWidget);
    updateSpacingLabels();
}

void TaskPatternParameters::setupParameterUI(QWidget* widget)
{
    ui->setupUi(widget);  // Setup the Task's own minimal UI (placeholder)
    // Only a standalone pattern picks its own features and has options; MultiTransform
    // owns both for its steps
    ui->featuresPlaceholder->hide();
    ui->optionsPlaceholder->hide();
    QMetaObject::connectSlotsByName(this);

    // --- Create and Embed the Parameter Widget ---
    auto pattern = getObject();
    if (!pattern) {
        return;
    }
    PartGui::PatternType type = pattern->isDerivedFrom<PartDesign::LinearPattern>()
        ? PartGui::PatternType::Linear
        : PartGui::PatternType::Polar;

    // Set first direction widget
    auto* viewer = getTopTransformedView()->getViewer();
    parametersWidget = new PartGui::PatternParametersWidget(type, viewer, widget);
    parametersWidget->setObjectName(QStringLiteral("patternDirection1"));

    auto* placeholderLayout = new QVBoxLayout(ui->parametersWidgetPlaceholder);
    placeholderLayout->setContentsMargins(0, 0, 0, 0);
    placeholderLayout->addWidget(parametersWidget);
    ui->parametersWidgetPlaceholder->setLayout(placeholderLayout);

    auto* sketch = dynamic_cast<Part::Part2DObject*>(getSketchObject());
    this->fillAxisCombo(parametersWidget->dirLinks, sketch);
    connect(
        parametersWidget,
        &PartGui::PatternParametersWidget::pickRequested,
        this,
        &TaskPatternParameters::onParameterWidgetRequestReferenceSelection
    );
    connect(
        parametersWidget,
        &PartGui::PatternParametersWidget::parametersChanged,
        this,
        &TaskPatternParameters::onParameterWidgetParametersChanged
    );

    // Add second direction widget if necessary
    if (type == PartGui::PatternType::Linear) {
        parametersWidget2 = new PartGui::PatternParametersWidget(type, viewer, widget);
        parametersWidget2->setObjectName(QStringLiteral("patternDirection2"));
        auto* placeholderLayout2 = new QVBoxLayout(ui->parametersWidgetPlaceholder2);
        placeholderLayout2->setContentsMargins(0, 0, 0, 0);
        placeholderLayout2->addWidget(parametersWidget2);
        ui->parametersWidgetPlaceholder2->setLayout(placeholderLayout2);

        this->fillAxisCombo(parametersWidget2->dirLinks, sketch);
        connect(
            parametersWidget2,
            &PartGui::PatternParametersWidget::pickRequested,
            this,
            &TaskPatternParameters::onParameterWidgetRequestReferenceSelection2
        );
        connect(
            parametersWidget2,
            &PartGui::PatternParametersWidget::parametersChanged,
            this,
            &TaskPatternParameters::onParameterWidgetParametersChanged
        );
        connect(
            parametersWidget2,
            &PartGui::PatternParametersWidget::directionQuickPicked,
            this,
            &TaskPatternParameters::onSecondDirectionFilled
        );
        parametersWidget2->setTitle(tr("Direction 2"));
        parametersWidget2->setClearable(true);
        parametersWidget2->setPlaceholder(tr("Click an edge to add"));
    }

    bindProperties();

    // --- Task Specific Setup ---
    showOriginAxes(true);  // Show origin helper axes

    updateViewTimer = new QTimer(this);
    updateViewTimer->setSingleShot(true);
    // Quick enough that the preview keeps up with typing and dragging
    updateViewTimer->setInterval(previewDelayMs);
    connect(updateViewTimer, &QTimer::timeout, this, &TaskPatternParameters::onUpdateViewTimer);
}

void TaskPatternParameters::bindProperties()
{
    auto pattern = getObject();
    if (!pattern) {
        return;
    }

    if (pattern->isDerivedFrom<PartDesign::LinearPattern>()) {
        auto* linear = static_cast<PartDesign::LinearPattern*>(pattern);
        parametersWidget->bindProperties(
            &linear->Direction,
            &linear->Reversed,
            &linear->Part::LinearPatternExtension::Mode,
            &linear->Length,
            &linear->Offset,
            &linear->Spacings,
            &linear->SpacingPattern,
            &linear->Occurrences,
            linear
        );
        parametersWidget2->bindProperties(
            &linear->Direction2,
            &linear->Reversed2,
            &linear->Mode2,
            &linear->Length2,
            &linear->Offset2,
            &linear->Spacings2,
            &linear->SpacingPattern2,
            &linear->Occurrences2,
            linear
        );
    }
    else if (pattern->isDerivedFrom<PartDesign::PolarPattern>()) {
        auto* polar = static_cast<PartDesign::PolarPattern*>(pattern);
        parametersWidget->bindProperties(
            &polar->Axis,
            &polar->Reversed,
            &polar->Part::PolarPatternExtension::Mode,
            &polar->Angle,
            &polar->Offset,
            &polar->Spacings,
            &polar->SpacingPattern,
            &polar->Occurrences,
            polar
        );
    }
    else {
        Base::Console().warning(
            "PatternParametersWidget property binding failed. Something is wrong please report.\n"
        );
    }
}

void TaskPatternParameters::retranslateParameterUI(QWidget* widget)
{
    ui->retranslateUi(widget);
}

void TaskPatternParameters::updateUI()
{
    if (parametersWidget) {
        parametersWidget->updateUI();
    }
    if (parametersWidget2) {
        parametersWidget2->updateUI();
    }
}

// --- Task-Specific Logic ---

void TaskPatternParameters::showOriginAxes(bool show)
{
    PartDesign::Body* body = PartDesign::Body::findBodyOf(getObject());
    if (body) {
        try {
            App::Origin* origin = body->getOrigin();
            auto vpOrigin = static_cast<ViewProviderCoordinateSystem*>(
                Gui::Application::Instance->getViewProvider(origin)
            );
            if (show) {
                vpOrigin->setTemporaryVisibility(Gui::DatumElement::Axes);
            }
            else {
                vpOrigin->resetTemporaryVisibility();
            }
        }
        catch (const Base::Exception& ex) {
            Base::Console().error("TaskPatternParameters: Error accessing origin axes: %s\n", ex.what());
        }
    }
}

// --- SLOTS ---

void TaskPatternParameters::onUpdateViewTimer()
{
    // Recompute is triggered when parameters change and this timer fires
    setupTransaction();  // Group potential property changes
    recomputeFeature();

    updateSpacingLabels();

    updateUI();
    setGizmoPositions();
}

void TaskPatternParameters::onParameterWidgetRequestReferenceSelection()
{
    setPickTarget(target == PickTarget::Direction1 ? PickTarget::None : PickTarget::Direction1);
}

void TaskPatternParameters::onParameterWidgetRequestReferenceSelection2()
{
    setPickTarget(target == PickTarget::Direction2 ? PickTarget::None : PickTarget::Direction2);
}

void TaskPatternParameters::setPickTarget(PickTarget next)
{
    if (next == target) {
        return;
    }

    if (target != PickTarget::None) {
        exitSelectionMode();
        // Back to what showed before the pick, as the Preview panel had it
        if (objectShownBeforePick) {
            showObject();
        }
        else {
            hideObject();
        }
        if (baseShownBeforePick) {
            showBase();
        }
        else {
            hideBase();
        }
        Gui::getMainWindow()->hideHints();
        // Esc's own release, still to come, must reach this filter too
        if (!eatEscapeRelease) {
            qApp->removeEventFilter(this);
        }
    }

    target = next;
    if (featuresField) {
        featuresField->setActive(target == PickTarget::Features);
    }
    if (parametersWidget) {
        parametersWidget->setPicking(target == PickTarget::Direction1);
    }
    if (parametersWidget2) {
        parametersWidget2->setPicking(target == PickTarget::Direction2);
    }

    if (target != PickTarget::None) {
        // The originals are what gets clicked, so they are shown instead of the result
        // until the pick ends
        App::DocumentObject* shown = getTopTransformedObject();
        App::DocumentObject* base = getBaseObject();
        objectShownBeforePick = shown && shown->Visibility.getValue();
        baseShownBeforePick = base && base->Visibility.getValue();
        hideObject();
        showBase();
        Gui::Selection().clearSelection();
        if (target == PickTarget::Features) {
            selectionMode = SelectionMode::AddFeature;
            // Only a feature of this body, and not one that already depends on this
            // pattern (which would make a cycle) - the same combination
            // addReferenceSelectionGate() builds for a direction reference
            std::unique_ptr<Gui::SelectionFilterGate> featureGate(
                new PatternFeatureGate(PartDesign::Body::findBodyOf(getObject()))
            );
            std::unique_ptr<Gui::SelectionFilterGate> dependentsGate(
                new NoDependentsSelection(getTopTransformedObject())
            );
            Gui::Selection().addSelectionGate(
                new CombineSelectionFilterGates(featureGate, dependentsGate)
            );
        }
        else {
            selectionMode = SelectionMode::Reference;
            const bool isPolar = getObject<PartDesign::PolarPattern>();
            addReferenceSelectionGate(
                AllowSelection::EDGE | AllowSelection::PLANAR
                | (isPolar ? AllowSelection::CIRCLE : AllowSelection::FACE)
            );
        }
        // The field takes the keyboard, so an arrow's value box that had it lets go and
        // hides with the arrows (a box with the keyboard stays on screen)
        PartGui::PickField* field = target == PickTarget::Features ? featuresField
            : target == PickTarget::Direction1                     ? parametersWidget->pickField()
            : parametersWidget2                                    ? parametersWidget2->pickField()
                                                                   : nullptr;
        if (field) {
            field->setFocus(Qt::OtherFocusReason);
        }
        showPickHints();
        // Esc turns the field off wherever the keyboard is, before the task panel or the
        // view can take it as Cancel
        qApp->installEventFilter(this);
    }

    updateFeaturesField();
    setGizmoPositions();
    Q_EMIT pickTargetChanged();
}

void TaskPatternParameters::showPickHints()
{
    using enum Gui::InputHint::UserInput;
    QString what = tr("%1 pick an edge or face for the direction");
    if (target == PickTarget::Features) {
        what = tr("%1 add or remove a feature");
    }
    else if (getObject<PartDesign::PolarPattern>()) {
        what = tr("%1 pick the axis");
    }
    Gui::getMainWindow()->showHints({
        {.message = what, .sequences = {MouseLeft}},
        {.message = tr("%1 stop picking"), .sequences = {KeyEscape}},
    });
}

bool TaskPatternParameters::eventFilter(QObject* watched, QEvent* event)
{
    const bool escape = (event->type() == QEvent::ShortcutOverride
                         || event->type() == QEvent::KeyPress
                         || event->type() == QEvent::KeyRelease)
        && static_cast<QKeyEvent*>(event)->key() == Qt::Key_Escape;
    if (!escape || QApplication::mouseButtons() != Qt::NoButton) {
        return TaskTransformedParameters::eventFilter(watched, event);
    }

    if (event->type() == QEvent::KeyRelease) {
        // A real release follows its press by roughly 100 ms - long after the press
        // below has already turned the field off and its 0 ms timer has run. Without
        // this flag the filter would already be gone by the time the release arrives,
        // so it would reach the view instead and be taken there as Cancel.
        if (!eatEscapeRelease) {
            return TaskTransformedParameters::eventFilter(watched, event);
        }
        eatEscapeRelease = false;
        if (target == PickTarget::None) {
            qApp->removeEventFilter(this);
        }
        return true;
    }

    // A popup (the quick picks) or a dialog (the formula editor) closes on its own Esc, and
    // that key's release is then left alone too, as eatEscapeRelease stays unset
    if (target == PickTarget::None || QApplication::activePopupWidget()
        || QApplication::activeModalWidget()) {
        return TaskTransformedParameters::eventFilter(watched, event);
    }

    if (event->type() == QEvent::ShortcutOverride) {
        // Taken as a plain key press, which comes back here next, not as a shortcut
        event->accept();
    }
    else {
        eatEscapeRelease = true;
        QTimer::singleShot(0, this, [this]() { setPickTarget(PickTarget::None); });
    }
    return true;
}

void TaskPatternParameters::setupFeaturesAndOptions()
{
    using Mode = PartDesign::Transformed::Mode;

    featuresField = new PartGui::PickField({}, ui->featuresPlaceholder);
    featuresField->setObjectName(QStringLiteral("pickFeatures"));
    featuresField->setPlaceholder(tr("Pick the features to copy"));
    auto* featuresLayout = new QVBoxLayout(ui->featuresPlaceholder);
    featuresLayout->setContentsMargins(0, 0, 0, 0);
    featuresLayout->addWidget(new QLabel(tr("Features"), ui->featuresPlaceholder));
    featuresLayout->addWidget(featuresField);
    ui->featuresPlaceholder->show();
    connect(featuresField, &PartGui::PickField::activationRequested, this, [this]() {
        setPickTarget(target == PickTarget::Features ? PickTarget::None : PickTarget::Features);
    });

    auto* toggle = new QToolButton(ui->optionsPlaceholder);
    toggle->setObjectName(QStringLiteral("optionsToggle"));
    toggle->setText(tr("Options"));
    toggle->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
    toggle->setArrowType(Qt::RightArrow);
    toggle->setCheckable(true);
    toggle->setAutoRaise(true);
    auto* box = new QWidget(ui->optionsPlaceholder);
    auto* boxLayout = new QVBoxLayout(box);
    boxLayout->setContentsMargins(12, 0, 0, 0);
    wholeBodyCheck = new QCheckBox(tr("Copy the whole body"), box);
    wholeBodyCheck->setObjectName(QStringLiteral("optionWholeBody"));
    updateViewCheck = new QCheckBox(tr("Recompute on change"), box);
    updateViewCheck->setObjectName(QStringLiteral("optionUpdateView"));
    updateViewCheck->setChecked(true);
    boxLayout->addWidget(wholeBodyCheck);
    boxLayout->addWidget(updateViewCheck);
    box->hide();
    auto* optionsLayout = new QVBoxLayout(ui->optionsPlaceholder);
    optionsLayout->setContentsMargins(0, 0, 0, 0);
    optionsLayout->addWidget(toggle);
    optionsLayout->addWidget(box);
    ui->optionsPlaceholder->show();
    connect(toggle, &QToolButton::toggled, box, [toggle, box](bool open) {
        box->setVisible(open);
        toggle->setArrowType(open ? Qt::DownArrow : Qt::RightArrow);
    });

    const bool whole = static_cast<Mode>(getObject()->TransformMode.getValue()) == Mode::WholeShape;
    wholeBodyCheck->setChecked(whole);
    // A choice other than the default stays in sight
    toggle->setChecked(whole);

    connect(wholeBodyCheck, &QCheckBox::toggled, this, [this](bool wholeBody) {
        if (!wholeBody && getObject()->Originals.getValues().empty()) {
            // Nothing to copy yet: stay on the body until a feature has been picked
            QSignalBlocker blocker(wholeBodyCheck);
            wholeBodyCheck->setChecked(true);
            setPickTarget(PickTarget::Features);
            return;
        }
        setPickTarget(PickTarget::None);
        setTransformMode(wholeBody ? Mode::WholeShape : Mode::Features);
        updateFeaturesField();
    });
    connect(updateViewCheck, &QCheckBox::toggled, this, &TaskPatternParameters::onUpdateView);

    updateFeaturesField();
}

void TaskPatternParameters::updateFeaturesField()
{
    if (!featuresField) {
        return;
    }
    using Mode = PartDesign::Transformed::Mode;
    auto* pattern = getObject();
    const bool whole = static_cast<Mode>(pattern->TransformMode.getValue()) == Mode::WholeShape;

    QStringList labels;
    for (App::DocumentObject* obj : pattern->Originals.getValues()) {
        labels << QString::fromUtf8(obj->Label.getValue());
    }
    featuresField->setSummary(whole ? tr("The whole body") : labels.join(QStringLiteral(", ")));
    featuresField->setEnabled(!whole || target == PickTarget::Features);
}

void TaskPatternParameters::toggleFeature(const Gui::SelectionChanges& msg)
{
    using Mode = PartDesign::Transformed::Mode;
    auto* pattern = getObject();
    if (!pattern || std::strcmp(msg.pDocName, pattern->getDocument()->getName()) != 0) {
        return;
    }
    App::DocumentObject* picked = pattern->getDocument()->getObject(msg.pObjectName);
    if (!picked || !picked->isDerivedFrom<PartDesign::FeatureAddSub>()) {
        return;
    }

    const bool whole = static_cast<Mode>(pattern->TransformMode.getValue()) == Mode::WholeShape;
    std::vector<App::DocumentObject*> originals = pattern->Originals.getValues();
    auto found = std::ranges::find(originals, picked);
    if (found == originals.end()) {
        originals.push_back(picked);
    }
    else if (!whole) {
        if (originals.size() == 1) {
            // With nothing to copy the pattern would be taken for a MultiTransform step
            Gui::getMainWindow()->showMessage(
                tr("A pattern needs at least one feature. To copy the whole body, use Options."),
                4000
            );
            return;
        }
        originals.erase(found);
    }

    setupTransaction();
    pattern->Originals.setValues(originals);
    if (whole) {
        setTransformMode(Mode::Features);
        QSignalBlocker blocker(wholeBodyCheck);
        wholeBodyCheck->setChecked(false);
    }
    recomputeFeature();
    setGizmoPositions();
    updateFeaturesField();
    // Cleared once this notification is over, so the same feature can be clicked again
    QTimer::singleShot(0, this, []() { Gui::Selection().clearSelection(); });
}

void TaskPatternParameters::startSecondDirection(PartDesign::LinearPattern* pattern)
{
    pattern->Mode2.setValue(static_cast<long>(Part::LinearPatternMode::Spacing));
    auto* body = PartDesign::Body::findBodyOf(pattern);
    const bool allowGaps = !body || body->AllowCompound.getValue();
    const Base::Vector3d direction =
        PartDesignGui::patternDirection(*pattern, pattern->Direction2).value_or(Base::Vector3d(0, 1, 0));

    std::vector<App::DocumentObject*> originals = pattern->getOriginals();
    double spacing;
    if (!originals.empty()) {
        spacing = PartDesignGui::suggestPatternSpacing(originals, direction, allowGaps);
    }
    else if (auto* base = pattern->getBaseObject(/* silent = */ true)) {
        // Whole-body mode: Originals is empty, so size from the base shape instead, the
        // way getStartPoint() falls back to it.
        spacing =
            PartDesignGui::suggestPatternSpacing(base->Shape.getShape().getShape(), direction, allowGaps);
    }
    else {
        spacing = PartDesignGui::suggestPatternSpacing(originals, direction, allowGaps);
    }
    pattern->Offset2.setValue(spacing);

    if (pattern->Occurrences2.getValue() < 2) {
        pattern->Occurrences2.setValue(2);
    }
}

void TaskPatternParameters::onSecondDirectionFilled(bool wasInUse)
{
    auto* pattern = getObject<PartDesign::LinearPattern>();
    if (wasInUse || !pattern) {
        return;
    }
    startSecondDirection(pattern);
    if (parametersWidget2) {
        parametersWidget2->updateUI();
    }
}

void TaskPatternParameters::onParameterWidgetParametersChanged()
{
    // A parameter in the embedded widget changed, trigger a recompute
    if (blockUpdate) {
        return;  // Avoid loops if change originated from Task update
    }
    kickUpdateViewTimer();  // Debounce recompute
}

void TaskPatternParameters::onUpdateView(bool on)
{
    // This might be less relevant now if recomputes are triggered by parametersChanged
    blockUpdate = !on;
    if (on) {
        kickUpdateViewTimer();
    }
}

void TaskPatternParameters::kickUpdateViewTimer() const
{
    updateViewTimer->start();
}

void TaskPatternParameters::onSelectionChanged(const Gui::SelectionChanges& msg)
{
    if (target == PickTarget::None || msg.Type != Gui::SelectionChanges::AddSelection) {
        return;
    }
    if (target == PickTarget::Features) {
        toggleFeature(msg);
        return;
    }

    auto patternObj = getObject();
    if (!patternObj) {
        return;
    }

    std::vector<std::string> directions;
    App::DocumentObject* selObj = nullptr;
    getReferencedSelection(patternObj, msg, selObj, directions);
    if (!selObj) {
        Base::Console().warning(
            tr("Invalid selection. Select an edge, planar face, or datum line.").toStdString().c_str()
        );
        return;
    }

    // Note: ReferenceSelection has already checked the selection for validity
    if (selectionMode == SelectionMode::Reference || selObj->isDerivedFrom<App::Line>()) {
        setupTransaction();

        if (patternObj->isDerivedFrom<PartDesign::LinearPattern>()) {
            auto* linearPattern = static_cast<PartDesign::LinearPattern*>(patternObj);
            if (target == PickTarget::Direction1) {
                linearPattern->Direction.setValue(selObj, directions);
            }
            else {
                const bool wasInUse = parametersWidget2->isInUse();
                linearPattern->Direction2.setValue(selObj, directions);
                onSecondDirectionFilled(wasInUse);
            }
        }
        else if (patternObj->isDerivedFrom<PartDesign::PolarPattern>()) {
            auto* polarPattern = static_cast<PartDesign::PolarPattern*>(patternObj);
            polarPattern->Axis.setValue(selObj, directions);
        }
        recomputeFeature();
        updateUI();
        setGizmoPositions();
    }
    setPickTarget(PickTarget::None);
}

TaskPatternParameters::~TaskPatternParameters()
{
    // The drag callbacks carry this panel, so they go before anything here does
    for (Gui::LinearGizmo* arrow : {arrow1, arrow2}) {
        if (arrow) {
            SoLinearDragger* dragger = arrow->getDraggerContainer()->getDragger();
            dragger->removeStartCallback(arrowDragStarted, this);
            dragger->removeFinishCallback(arrowDragFinished, this);
        }
    }
    if (handle) {
        SoRotationDragger* dragger = handle->getDraggerContainer()->getDragger();
        dragger->removeStartCallback(handleDragStarted, this);
        dragger->removeFinishCallback(handleDragFinished, this);
    }
    qApp->removeEventFilter(this);
    if (target != PickTarget::None) {
        Gui::Selection().rmvSelectionGate();
        if (auto* mainWindow = Gui::getMainWindow()) {
            mainWindow->hideHints();
        }
    }
    showOriginAxes(false);
}

void TaskPatternParameters::apply()
{
    auto pattern = getObject();
    if (!pattern || !parametersWidget) {
        return;
    }

    std::vector<std::string> dirs;
    App::DocumentObject* obj = nullptr;
    parametersWidget->getAxis(obj, dirs);
    std::string direction = buildLinkSingleSubPythonStr(obj, dirs);

    bool isLinear = pattern->isDerivedFrom<PartDesign::LinearPattern>();
    const char* propName = isLinear ? "Direction = " : "Axis = ";

    FCMD_OBJ_CMD(pattern, propName << direction.c_str());
    FCMD_OBJ_CMD(pattern, "Reversed = " << parametersWidget->getReverse());
    FCMD_OBJ_CMD(pattern, "Mode = " << parametersWidget->getMode());
    parametersWidget->applyQuantitySpinboxes();

    FCMD_OBJ_CMD(pattern, "SpacingPattern = " << parametersWidget->getSpacingPatternsAsString());

    if (parametersWidget2) {
        parametersWidget2->getAxis(obj, dirs);
        if (obj) {
            direction = buildLinkSingleSubPythonStr(obj, dirs);
            FCMD_OBJ_CMD(pattern, "Direction2 = " << direction.c_str());
        }
        else {
            FCMD_OBJ_CMD(pattern, "Direction2 = None");
        }
        FCMD_OBJ_CMD(pattern, "Reversed2 = " << parametersWidget2->getReverse());
        FCMD_OBJ_CMD(pattern, "Mode2 = " << parametersWidget2->getMode());
        parametersWidget2->applyQuantitySpinboxes();

        FCMD_OBJ_CMD(pattern, "SpacingPattern2 = " << parametersWidget2->getSpacingPatternsAsString());
    }

    // The user may have changed a value and immediately hit 'OK' or Enter.
    // This triggers accept() before the update timer for the 3D view has a
    // chance to fire. If the timer is active, it means a recompute is
    // pending.
    if (updateViewTimer && updateViewTimer->isActive()) {
        updateViewTimer->stop();
        recomputeFeature();
    }
}

void TaskPatternParameters::updateSpacingLabels()
{
    // A broken pattern (its spacing dragged down to zero, say) has nothing to measure,
    // and asking it for its steps throws; that must not escape into Qt and cut short the
    // update that hides a broken pattern's gizmos
    try {
        placeSpacingLabels();
    }
    catch (const Base::Exception&) {
        if (parametersWidget) {
            parametersWidget->clearAllSpacingLabels();
        }
        if (parametersWidget2) {
            parametersWidget2->clearAllSpacingLabels();
        }
    }
}

void TaskPatternParameters::placeSpacingLabels()
{
    Base::Vector3d startPoint = getStartPoint();

    if (auto* linearPattern = getObject<PartDesign::LinearPattern>()) {
        // Handle first direction widget
        if (parametersWidget) {
            // Get the direction vector using the feature's public method.
            // calculateOffsetVector returns a vector whose magnitude is one step in 'Extent' mode,
            // or a normalized vector in 'Spacing' mode. We normalize it to be safe.
            gp_Vec offset1 = linearPattern->calculateOffsetVector(Part::LinearPatternDirection::First);
            Base::Vector3d direction1(0, 0, 1);  // Default direction
            if (offset1.Magnitude() > Precision::Confusion()) {
                offset1.Normalize();
                direction1.x = offset1.X();
                direction1.y = offset1.Y();
                direction1.z = offset1.Z();
            }
            parametersWidget->updateSpacingLabels(startPoint, direction1);
        }

        // Handle second direction widget
        if (parametersWidget2) {
            gp_Vec offset2 = linearPattern->calculateOffsetVector(Part::LinearPatternDirection::Second);
            Base::Vector3d direction2(0, 1, 0);  // Default direction
            if (offset2.Magnitude() > Precision::Confusion()) {
                offset2.Normalize();
                direction2.x = offset2.X();
                direction2.y = offset2.Y();
                direction2.z = offset2.Z();
            }
            parametersWidget2->updateSpacingLabels(startPoint, direction2);
        }
        return;
    }

    if (auto* polarPattern = getObject<PartDesign::PolarPattern>()) {
        gp_Ax2 axisDef = polarPattern->getRotation();
        axisDef.Transform(polarPattern->getLocation().Transformation());

        gp_Pnt center_gp = axisDef.Location();
        gp_Dir axis_gp = axisDef.Direction();
        Base::Vector3d center(center_gp.X(), center_gp.Y(), center_gp.Z());
        Base::Vector3d axis(axis_gp.X(), axis_gp.Y(), axis_gp.Z());

        // Calculate X-axis for angular reference in the rotation plane
        Base::Rotation labelRot(Base::Vector3d(0.0, 0.0, 1.0), axis);
        Base::Vector3d xDir;
        labelRot.multVec(Base::Vector3d(1.0, 0.0, 0.0), xDir);

        Base::Vector3d startRadiusVec = startPoint - center;
        double radius = startRadiusVec.Length();
        if (radius < Precision::Confusion()) {
            radius = 1.0;
        }

        double initialAngle_rad = 0.0;
        Base::Vector3d projectedRadiusVec = startRadiusVec - (startRadiusVec.Dot(axis)) * axis;
        if (projectedRadiusVec.Length() > 1e-6) {
            initialAngle_rad = xDir.GetAngleOriented(projectedRadiusVec, axis);
        }

        if (parametersWidget) {
            parametersWidget->updateSpacingLabels(center, axis, radius, initialAngle_rad);
        }
    }
}

Base::Vector3d TaskPatternParameters::getStartPoint() const
{
    Base::Vector3d startPoint(0, 0, 0);

    auto* pattern = dynamic_cast<PartDesign::Transformed*>(getObject());
    if (!pattern) {
        return startPoint;
    }

    std::vector<App::DocumentObject*> originals = pattern->getOriginals();
    BRep_Builder builder;
    TopoDS_Compound compoundShape;
    builder.MakeCompound(compoundShape);
    bool any = false;
    for (App::DocumentObject* obj : originals) {
        // We are only interested in additive/subtractive features.
        if (auto* addSubFeature = dynamic_cast<PartDesign::FeatureAddSub*>(obj)) {
            TopoDS_Shape shape = addSubFeature->AddSubShape.getShape().getShape();
            if (!shape.IsNull()) {
                shape.Move(addSubFeature->getLocation());
                builder.Add(compoundShape, shape);
                any = true;
            }
        }
    }
    if (!any) {
        // The whole body: its shape before this pattern
        if (auto* base = pattern->getBaseObject(/* silent = */ true)) {
            TopoDS_Shape shape = base->Shape.getShape().getShape();
            if (!shape.IsNull()) {
                builder.Add(compoundShape, shape);
                any = true;
            }
        }
    }
    if (any) {
        // Calculate the center of the combined bounding box.
        try {
            Bnd_Box bndBox;
            BRepBndLib::Add(compoundShape, bndBox);
            if (!bndBox.IsVoid()) {
                double xmin, ymin, zmin, xmax, ymax, zmax;
                bndBox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
                startPoint.x = (xmin + xmax) / 2.0;
                startPoint.y = (ymin + ymax) / 2.0;
                startPoint.z = (zmin + zmax) / 2.0;
            }
        }
        catch (const Base::Exception& e) {
            Base::Console().warning(
                "Could not calculate center of patterned features: %s\n",
                e.what()
            );
            // startPoint remains (0,0,0) as a fallback.
        }
    }
    return startPoint;
}

void TaskPatternParameters::setupGizmos()
{
    if (!Gui::GizmoContainer::isEnabled()) {
        return;
    }

    const auto toggleReversed = [](PartGui::PatternParametersWidget* widget) {
        return [widget]() {
            if (auto* field = widget->pickField()) {
                Q_EMIT field->reverseClicked();
            }
        };
    };

    const auto bindCount = [](Gui::Gizmo* gizmo, PartGui::PatternParametersWidget* widget) {
        Gui::UIntSpinBox* box = widget->countBox();
        // The box in the view takes the panel box's range, capped the same way
        gizmo->setCountBinding(
            [box]() { return static_cast<int>(box->value()); },
            [box](int count) { box->setValue(static_cast<uint>(count)); },
            static_cast<int>(box->minimum()),
            static_cast<int>(box->maximum())
        );
    };

    if (getObject<PartDesign::PolarPattern>()) {
        handle = new Gui::RadialGizmo(parametersWidget->activeValueBox());
        handle->setClickCallback(toggleReversed(parametersWidget));
        gizmoContainer = Gui::GizmoContainer::create({handle}, TransformedView);
        // The arrow points the way the copies go, as on Revolve
        handle->flipArrow();
        bindCount(handle, parametersWidget);
        parametersWidget->setGizmoCoversFirstLabel(Gui::GizmoContainer::isValueLabelsEnabled());
        updateSpacingLabels();

        // Both ends of a drag are reported, so the handle keeps its footing while it is
        // dragged, see setGizmoPositions - the same guard the arrows have, since turning
        // the angle to 0 makes the pattern throw and the 100 ms recompute must not hide
        // the handle out from under the drag
        SoRotationDragger* dragger = handle->getDraggerContainer()->getDragger();
        dragger->addStartCallback(handleDragStarted, this);
        dragger->addFinishCallback(handleDragFinished, this);

        setGizmoPositions();
        return;
    }

    if (!getObject<PartDesign::LinearPattern>()) {
        return;
    }

    arrow1 = new Gui::LinearGizmo(parametersWidget->activeValueBox());
    arrow1->setClickCallback(toggleReversed(parametersWidget));
    arrow2 = new Gui::LinearGizmo(parametersWidget2->activeValueBox());
    arrow2->setClickCallback(toggleReversed(parametersWidget2));
    gizmoContainer = Gui::GizmoContainer::create({arrow1, arrow2}, TransformedView);

    bindCount(arrow1, parametersWidget);
    bindCount(arrow2, parametersWidget2);

    // Both ends of a drag are reported, so an arrow keeps its footing while it is
    // dragged, see setGizmoPositions
    for (Gui::LinearGizmo* arrow : {arrow1, arrow2}) {
        SoLinearDragger* dragger = arrow->getDraggerContainer()->getDragger();
        dragger->addStartCallback(arrowDragStarted, this);
        dragger->addFinishCallback(arrowDragFinished, this);
    }

    const bool covered = Gui::GizmoContainer::isValueLabelsEnabled();
    parametersWidget->setGizmoCoversFirstLabel(covered);
    parametersWidget2->setGizmoCoversFirstLabel(covered);
    updateSpacingLabels();

    setGizmoPositions();
}

void TaskPatternParameters::setGizmoPositions()
{
    if (!gizmoContainer) {
        return;
    }
    // An arrow or the handle being dragged is left alone, even when the pattern breaks
    // under it (its spacing or angle pulled down to zero): the dragger holds the mouse
    // from inside the container's switch, and closing that switch cuts the drag's path
    // short, as on Extrude. Letting go puts everything right, see arrowDragFinished and
    // handleDragFinished
    if (draggingGizmo) {
        return;
    }
    auto* feature = getObject();
    if (!feature || feature->isError() || target != PickTarget::None) {
        gizmoContainer->visible = false;
        return;
    }
    gizmoContainer->visible = true;

    if (auto* polar = getObject<PartDesign::PolarPattern>()) {
        placePolarHandle(polar);
    }
    else if (auto* pattern = getObject<PartDesign::LinearPattern>()) {
        placeLinearArrows(pattern);
    }
    // A newly shown arrow, or one turned round by Reversed, is sized and faced for the
    // camera now rather than at its next move, as on Extrude
    gizmoContainer->calculateScaleAndOrientation();
}

void TaskPatternParameters::placeLinearArrows(PartDesign::LinearPattern* pattern)
{
    const Base::Vector3d start = getStartPoint();
    const auto place = [&](Gui::LinearGizmo* arrow,
                           PartGui::PatternParametersWidget* widget,
                           const App::PropertyLinkSub& link,
                           bool reversed) {
        // The arrow drives whichever value the mode shows, and a drag in progress is
        // never moved under the pointer: its base and direction only change on a new pick
        if (arrow->getProperty() != widget->activeValueBox()) {
            arrow->setProperty(widget->activeValueBox());
        }
        std::optional<Base::Vector3d> dir = PartDesignGui::patternDirection(*pattern, link);
        const bool shown = dir.has_value() && widget->isInUse();
        arrow->setVisibility(shown);
        if (!shown) {
            return;
        }
        Base::Vector3d along = reversed ? -*dir : *dir;
        Gui::GizmoPlacement now = arrow->getDraggerPlacement();
        const SbVec3f pos(start.x, start.y, start.z);
        const SbVec3f vec(along.x, along.y, along.z);
        if (!now.pos.equals(pos, 1e-6F) || !now.dir.equals(vec, 1e-6F)) {
            arrow->Gizmo::setDraggerPlacement(start, along);
        }
        arrow->updateValueLabel();
    };
    place(arrow1, parametersWidget, pattern->Direction, pattern->Reversed.getValue());
    place(arrow2, parametersWidget2, pattern->Direction2, pattern->Reversed2.getValue());
}

void TaskPatternParameters::placePolarHandle(PartDesign::PolarPattern* polar)
{
    if (handle->getProperty() != parametersWidget->activeValueBox()) {
        handle->setProperty(parametersWidget->activeValueBox());
    }

    Base::Vector3d centre;
    Base::Vector3d axis;
    try {
        gp_Ax2 axisDef = polar->getRotation();
        axisDef.Transform(polar->getLocation().Transformation());
        centre = Base::Vector3d(axisDef.Location().X(), axisDef.Location().Y(), axisDef.Location().Z());
        axis = Base::Vector3d(axisDef.Direction().X(), axisDef.Direction().Y(), axisDef.Direction().Z());
    }
    catch (const Base::Exception&) {
        handle->setVisibility(false);
        return;
    }
    catch (const Standard_Failure&) {
        handle->setVisibility(false);
        return;
    }
    // getRotation() already reverses the axis when Reversed is set
    // (PolarPatternExtension::getRotation), the same direction updateSpacingLabels
    // uses - reversing it again here would point the handle away from the copies

    // The handle turns about the axis, level with the features and out at their distance
    const Base::Vector3d offset = getStartPoint() - centre;
    const Base::Vector3d along = axis * offset.Dot(axis);
    const Base::Vector3d radial = offset - along;
    if (radial.Length() < Precision::Confusion()) {
        // Features centred on the axis: there is no side to put the handle on
        handle->setVisibility(false);
        return;
    }
    handle->setVisibility(true);

    // Always re-placed (unlike the linear arrows' place() lambda): the dragger's own
    // pointer direction is not a unit vector, so it can never be compared against
    // radial directly, and doing so would also miss an axis-only change (Reversed
    // toggled with the features' position unchanged) - Revolve's setGizmoPositions
    // re-places its own RadialGizmos unconditionally for the same reason
    const Base::Vector3d pivot = centre + along;
    handle->setRadius(static_cast<float>(radial.Length()));
    handle->Gizmo::setDraggerPlacement(pivot, radial);
    handle->getDraggerContainer()->setArcNormalDirection(Base::convertTo<SbVec3f>(axis));
    handle->updateValueLabel();
}

void TaskPatternParameters::arrowDragStarted(void* data, SoDragger*)
{
    static_cast<TaskPatternParameters*>(data)->draggingGizmo = true;
}

void TaskPatternParameters::arrowDragFinished(void* data, SoDragger*)
{
    auto* self = static_cast<TaskPatternParameters*>(data);
    self->draggingGizmo = false;
    // The arrows stayed where the drag found them: put them where the pattern ended
    // up, or away if it broke
    self->setGizmoPositions();
}

void TaskPatternParameters::handleDragStarted(void* data, SoDragger*)
{
    static_cast<TaskPatternParameters*>(data)->draggingGizmo = true;
}

void TaskPatternParameters::handleDragFinished(void* data, SoDragger*)
{
    auto* self = static_cast<TaskPatternParameters*>(data);
    self->draggingGizmo = false;
    // The handle stayed where the drag found it: put it where the pattern ended up,
    // or away if it broke (turning the angle to 0 throws, see setGizmoPositions)
    self->setGizmoPositions();
}

//**************************************************************************
// TaskDialog Implementation (Remains largely the same)
//**************************************************************************

TaskDlgLinearPatternParameters::TaskDlgLinearPatternParameters(
    ViewProviderTransformed* LinearPatternView
)
    : TaskDlgTransformedParameters(LinearPatternView)  // Use base class constructor
{
    // Create the specific parameter task panel
    parameter = new TaskPatternParameters(LinearPatternView);
    // Add it to the dialog's content list
    Content.push_back(parameter);
    Content.push_back(preview);
}

#include "moc_TaskPatternParameters.cpp"
